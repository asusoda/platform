# agents

Keeps what an org's agents know about the members they talk to: conversations, memories, a profile graph and pending actions. Members can see and delete their own agent data.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Agent routes under `/members/<discord_id>` and member routes under `/<org_prefix>/me` |
| `service.py` | `Owner`, `AgentError`, shared input checks and prune; declares the `agents:read` and `agents:write` scopes |
| `conversations.py`, `memories.py`, `pending.py` | Conversations with messages and summaries; memories (sensitive ones encrypted); actions held for confirmation |
| `profile.py` | The profile graph, nearest nodes by embedding, and deletes of a member's data |
| `turns.py` | The turn context an agent reads before its model call, and the turn commit in one transaction |
| `models.py` | Conversations, messages, memories, profile nodes and edges, pending actions |
| `jobs.py` | The prune job |

## Surface

- Routes: `/api/agents`. Agent routes need a machine token with `agents:read` or `agents:write` and act on the token's org. `/<org_prefix>/me` routes need a member's Discord session. Officers have no route to agent data.
- Jobs: `agents.prune`, schedule `15 4 * * *`.
- Tools: none.
- Tables: `agent_conversations`, `agent_messages`, `agent_memories`, `agent_profile_nodes`, `agent_profile_edges`, `agent_pending_actions`.

See [docs/modules/agents.md](../../docs/modules/agents.md).
