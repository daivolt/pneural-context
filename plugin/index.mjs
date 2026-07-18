const PNEURAL_URL = process.env.PNEURAL_CONTEXT_URL || "http://localhost:8778";
const PNEURAL_API_KEY = process.env.PNEURAL_API_KEY || "";
const TIMEOUT_MS = 5000;
const RECORD_TIMEOUT_MS = 30000;

const PB_INJECT_ON_START = process.env.PB_INJECT_ON_START !== "false";
const PB_INJECT_ON_COMPACT = process.env.PB_INJECT_ON_COMPACT !== "false";
const PB_RECORD_SESSIONS = process.env.PB_RECORD_SESSIONS === "true";
const PB_SESSION_RECORD_TYPE = process.env.PB_SESSION_RECORD_TYPE || "temporal";
const PB_SMART_DEDUP = process.env.PB_SMART_DEDUP !== "false";
const PB_DEDUP_MESSAGES = parseInt(process.env.PB_DEDUP_MESSAGES || "10", 10);

const CACHE_TTL_MS = 5 * 60 * 1000;

let contextCache = null;
let cacheTimestamp = 0;
let lastMarker = null;

let statusCache = null;
let statusCacheTimestamp = 0;
const STATUS_CACHE_TTL_MS = 30 * 1000;

let currentSessionId = null;

const authHeaders = () => {
  const h = { "Content-Type": "application/json" };
  if (PNEURAL_API_KEY) h["X-API-Key"] = PNEURAL_API_KEY;
  return h;
};

const resolveProject = (ctx) => {
  const fs = require("node:fs");
  const path = require("node:path");
  if (process.env.PNEURAL_PROJECT) return process.env.PNEURAL_PROJECT;
  const dir = ctx.directory || process.cwd();
  const configPath = path.join(dir, ".pneural-context.json");
  try {
    if (fs.existsSync(configPath)) {
      const cfg = JSON.parse(fs.readFileSync(configPath, "utf8"));
      if (cfg.project) return cfg.project;
    }
  } catch (_) {}
  return path.basename(dir) || "unknown";
};

const logError = async (project, source, message, stack) => {
  try {
    await fetch(`${PNEURAL_URL}/api/errors`, {
      method: "POST",
      headers: authHeaders(),
      signal: AbortSignal.timeout(3000),
      body: JSON.stringify({
        project,
        session_id: currentSessionId || "",
        source,
        level: "error",
        message: message.slice(0, 2000),
        stack: stack ? stack.slice(0, 4000) : "",
      }),
    });
  } catch (_) {}
};

const getJSON = async (urlPath, project) => {
  try {
    const resp = await fetch(`${PNEURAL_URL}${urlPath}`, {
      headers: authHeaders(),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`);
    }
    return await resp.json();
  } catch (err) {
    if (project) await logError(project, "plugin", `getJSON ${urlPath}: ${err.message}`, err.stack);
    return null;
  }
};

const postJSON = async (path, body, timeout = TIMEOUT_MS * 2, project) => {
  try {
    const resp = await fetch(`${PNEURAL_URL}${path}`, {
      method: "POST",
      headers: authHeaders(),
      signal: AbortSignal.timeout(timeout),
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`);
    }
    return await resp.json();
  } catch (err) {
    if (project) await logError(project, "plugin", `postJSON ${path}: ${err.message}`, err.stack);
    return null;
  }
};

const buildContextMarkdown = (project, entries) => {
  if (!entries || entries.length === 0) return null;
  const marker = require("node:crypto").randomBytes(4).toString("hex");
  const lines = [`<!-- PNEURAL_CTX: ${marker} -->`];
  lines.push(`# Context: ${project}`);
  lines.push("");
  const redInk = entries.filter(
    (e) => e.priority === "critical" && (e.strength ?? 1.0) >= 0.3
  );
  const byType = {};
  for (const e of entries) {
    if (e.priority === "critical" && (e.strength ?? 1.0) >= 0.3) continue;
    const t = e.memory_type || "temporal";
    byType[t] = byType[t] || [];
    byType[t].push(e);
  }
  if (redInk.length > 0) {
    lines.push("## Critical (Red Ink)");
    lines.push("");
    for (const e of redInk) lines.push(`- ${e.entry || e.content || ""}`);
    lines.push("");
  }
  for (const mtype of ["concept", "procedural", "temporal", "relation"]) {
    const group = byType[mtype] || [];
    if (group.length === 0) continue;
    lines.push(`## ${mtype.toUpperCase()}`);
    lines.push("");
    for (const e of group) lines.push(`- ${e.entry || e.content || ""}`);
    lines.push("");
  }
  return { markdown: lines.join("\n"), marker };
};

const isPneuralEnabled = async (project) => {
  const now = Date.now();
  if (statusCache && statusCache.project === project && now - statusCacheTimestamp < STATUS_CACHE_TTL_MS) {
    return statusCache.enabled;
  }
  const resp = await getJSON(`/api/status?project=${encodeURIComponent(project)}`, project);
  if (resp) {
    statusCache = { project, enabled: resp.enabled !== false };
    statusCacheTimestamp = now;
    return statusCache.enabled;
  }
  return true;
};

const fetchContext = async (project) => {
  const now = Date.now();
  if (contextCache && now - cacheTimestamp < CACHE_TTL_MS && lastMarker) {
    return { markdown: contextCache, marker: lastMarker };
  }
  const resp = await getJSON(`/api/context?project=${encodeURIComponent(project)}`, project);
  if (resp && resp.markdown) {
    contextCache = resp.markdown;
    lastMarker = resp.marker;
    cacheTimestamp = now;
    return { markdown: resp.markdown, marker: resp.marker };
  }
  return null;
};

const fetchSmartContext = async (project, conversation) => {
  if (!PB_SMART_DEDUP || !conversation) {
    return fetchContext(project);
  }
  const resp = await postJSON("/api/context/smart", {
    project,
    conversation,
  }, TIMEOUT_MS * 4, project);
  if (resp && resp.entries && resp.entries.length > 0) {
    const result = buildContextMarkdown(project, resp.entries);
    if (result) {
      contextCache = result.markdown;
      lastMarker = result.marker;
      cacheTimestamp = Date.now();
      return result;
    }
  }
  return fetchContext(project);
};

const collectConversationText = async (ctx, sessionId) => {
  try {
    if (!ctx?.client?.session?.messages) return "";
    const result = await ctx.client.session.messages({ path: { id: sessionId } });
    if (!result?.data) return "";
    const msgs = Array.isArray(result.data) ? result.data : [];
    const parts = [];
    for (const m of msgs.slice(-PB_DEDUP_MESSAGES)) {
      for (const p of m.parts || []) {
        if (p.type === "text" && p.text) {
          parts.push(`[${m.info?.role || "user"}] ${p.text.slice(0, 500)}`);
        }
      }
    }
    return parts.join("\n");
  } catch (_) {
    return "";
  }
};

export default async (ctx) => {
  const project = resolveProject(ctx);

  return {
    "experimental.chat.system.transform": async (_input, output) => {
      if (!PB_INJECT_ON_START) return;
      try {
        const enabled = await isPneuralEnabled(project);
        if (!enabled) return;
        const sessionId = _input?.session_id || _input?.id || "";
        if (sessionId) currentSessionId = sessionId;
        let conversation = "";
        if (PB_SMART_DEDUP && sessionId) {
          conversation = await collectConversationText(ctx, sessionId);
        }
        if (conversation) {
          const result = await fetchSmartContext(project, conversation);
          if (result && result.markdown) {
            output.system.push(result.markdown);
          }
        } else {
          const result = await fetchContext(project);
          if (result && result.markdown) {
            output.system.push(result.markdown);
          }
        }
      } catch (err) {
        await logError(project, "plugin", `system.transform: ${err.message}`, err.stack);
      }
    },

    "experimental.session.compacting": async (_input, output) => {
      if (!PB_INJECT_ON_COMPACT) return;
      try {
        const result = await fetchContext(project);
        if (result && result.marker) {
          output.context.push(
            `IMPORTANT: The system prompt contains a PNEURAL_CTX marker (${result.marker}). ` +
            `This marker and the Pinned Context section MUST be preserved verbatim in your summary. ` +
            `Do not omit or paraphrase the pinned context.`
          );
        }
      } catch (err) {
        await logError(project, "plugin", `compacting: ${err.message}`, err.stack);
      }
    },

    event: async ({ event: ev }) => {
      if (!ev || !ev.type) return;

      try {
        if (ev.type === "session.created") {
          currentSessionId = ev.properties?.info?.id || ev.properties?.sessionID || ev.properties?.id || "";
          if (PB_INJECT_ON_START) {
            await fetchContext(project);
          }
          return;
        }

        if (ev.type === "session.error" || ev.type === "error") {
          const msg = ev.properties?.message || ev.properties?.error || JSON.stringify(ev.properties || {});
          await logError(project, "opencode", `session.${ev.type}: ${msg.slice(0, 1000)}`, "");
          return;
        }

        if (ev.type === "session.idle" && PB_RECORD_SESSIONS) {
          const sessionId = ev.properties?.info?.id || ev.properties?.sessionID || ev.properties?.id;
          if (!sessionId) return;

          let title = ev.properties?.title || ev.properties?.info?.title || "";
          let messages = [];

          try {
            if (ctx.client && ctx.client.session && ctx.client.session.messages) {
              const result = await ctx.client.session.messages({ path: { id: sessionId } });
              if (result && result.data) {
                const msgs = Array.isArray(result.data) ? result.data : [];
                for (const m of msgs) {
                  const parts = m.parts || [];
                  for (const p of parts) {
                    if (p.type === "text" && p.text) {
                      messages.push({ role: m.info?.role || "user", content: p.text });
                    }
                  }
                }
              }
            }
          } catch (e) {
            await logError(project, "plugin", `session.messages: ${e.message}`, e.stack);
          }

          if (!title && messages.length > 0) {
            title = messages[0].content.slice(0, 80);
          }

          if (messages.length === 0) {
            messages.push({ role: "user", content: title || "empty session" });
          }

          await postJSON("/api/session/record", {
            project,
            session_id: sessionId,
            title,
            messages,
            memory_type: PB_SESSION_RECORD_TYPE,
          }, RECORD_TIMEOUT_MS, project);

          contextCache = null;
          cacheTimestamp = 0;
          lastMarker = null;
          return;
        }
      } catch (err) {
        await logError(project, "plugin", `event.${ev.type}: ${err.message}`, err.stack);
      }
    },
  };
};
