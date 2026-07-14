const PNEURAL_URL = process.env.PNEURAL_CONTEXT_URL || "http://localhost:8778";
const TIMEOUT_MS = 5000;
const RECORD_TIMEOUT_MS = 30000;

const PB_INJECT_ON_START = process.env.PB_INJECT_ON_START !== "false";
const PB_INJECT_ON_COMPACT = process.env.PB_INJECT_ON_COMPACT !== "false";
const PB_RECORD_SESSIONS = process.env.PB_RECORD_SESSIONS === "true";
const PB_SESSION_RECORD_TYPE = process.env.PB_SESSION_RECORD_TYPE || "temporal";

const CACHE_TTL_MS = 5 * 60 * 1000;

let contextCache = null;
let cacheTimestamp = 0;
let lastMarker = null;

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

const getJSON = async (urlPath) => {
  try {
    const resp = await fetch(`${PNEURAL_URL}${urlPath}`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch (_) {
    return null;
  }
};

const postJSON = async (path, body, timeout = TIMEOUT_MS * 2) => {
  try {
    const resp = await fetch(`${PNEURAL_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(timeout),
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`);
    }
    return await resp.json();
  } catch (_) {
    return null;
  }
};

const fetchContext = async (project) => {
  const now = Date.now();
  if (contextCache && now - cacheTimestamp < CACHE_TTL_MS && lastMarker) {
    return { markdown: contextCache, marker: lastMarker };
  }
  const resp = await getJSON(`/api/context?project=${encodeURIComponent(project)}`);
  if (resp && resp.markdown) {
    contextCache = resp.markdown;
    lastMarker = resp.marker;
    cacheTimestamp = now;
    return { markdown: resp.markdown, marker: resp.marker };
  }
  return null;
};

export default async (ctx) => {
  const project = resolveProject(ctx);

  return {
    "experimental.chat.system.transform": async (_input, output) => {
      if (!PB_INJECT_ON_START) return;
      const result = await fetchContext(project);
      if (result && result.markdown) {
        output.system.push(result.markdown);
      }
    },

    "experimental.session.compacting": async (_input, output) => {
      if (!PB_INJECT_ON_COMPACT) return;
      const result = await fetchContext(project);
      if (result && result.marker) {
        output.context.push(
          `IMPORTANT: The system prompt contains a PNEURAL_CTX marker (${result.marker}). ` +
          `This marker and the Pinned Context section MUST be preserved verbatim in your summary. ` +
          `Do not omit or paraphrase the pinned context.`
        );
      }
    },

    event: async ({ event: ev }) => {
      if (!ev || !ev.type) return;

      if (ev.type === "session.created") {
        if (PB_INJECT_ON_START) {
          await fetchContext(project);
        }
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
        } catch (_) {}

        if (!title && messages.length > 0) {
          title = messages[0].content.slice(0, 80);
        }

        if (messages.length === 0) {
          messages.push({ role: "user", content: title || "empty session" });
        }

        try {
          await postJSON("/api/session/record", {
            project,
            session_id: sessionId,
            title,
            messages,
            memory_type: PB_SESSION_RECORD_TYPE,
          }, RECORD_TIMEOUT_MS);
        } catch (_) {}

        contextCache = null;
        cacheTimestamp = 0;
        lastMarker = null;
        return;
      }
    },
  };
};