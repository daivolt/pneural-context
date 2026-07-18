# Enable/Disable Toggle

## Overview

Pneural-context can be toggled on/off per project mid-session without restarting
the server or opencode. When disabled, the plugin stops injecting PNEURAL_CTX
markers into the system prompt.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status?project=X` | GET | Check enabled/disabled state |
| `/api/status/disable` | POST | Disable for a project |
| `/api/status/enable` | POST | Enable for a project |
| `/api/status/toggle` | POST | Toggle between enabled/disabled |

All POST endpoints accept `{"project": "my-project"}` as JSON body.

## MCP Tools

- `pb_disable` — Disable context injection for a project
- `pb_enable` — Re-enable context injection
- `pb_status` — Check current enabled/disabled state

## Plugin Behavior

The plugin calls `/api/status?project=X` before every `system.transform` hook
injection. Results are cached for 30 seconds.

When disabled:
- No PNEURAL_CTX context block is injected
- Session recording is skipped
- Marker preservation during compaction is skipped

Changes take effect within 30 seconds (cache TTL) — no restart needed.

## Use Cases

- **Debugging**: Isolate whether context injection is causing issues
- **Performance**: Skip context for quick one-off queries
- **A/B Testing**: Toggle off treatment group in benchmarks
- **Clean sessions**: Start fresh without accumulated memory

## Examples

```bash
# Check state
curl http://localhost:8778/api/status?project=my-project
# {"project":"my-project","enabled":true}

# Disable
curl -X POST http://localhost:8778/api/status/disable \
  -H "Content-Type: application/json" \
  -d '{"project":"my-project"}'

# Re-enable
curl -X POST http://localhost:8778/api/status/enable \
  -H "Content-Type: application/json" \
  -d '{"project":"my-project"}'
```

## Implementation

State is stored **in-memory** (not persisted to DB). A server restart resets
all projects to enabled. `routers/status.py` maintains `_disabled_projects: set[str]`.
