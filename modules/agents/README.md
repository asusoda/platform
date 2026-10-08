# agents

Stores what an organization's agents keep about the members they talk to: conversations, messages, memories, a profile graph of facts, and pending actions waiting for confirmation. Members can see and delete their own agent data.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Agent routes under `/members/<discord_id>` (conversations, memories, profile, pending actions, turn context and commit) and member routes under `/<org_prefix>/me` |
| `service.py` | Storage scoped to one org and member, encryption of sensitive memories, pruning; declares the `agents:read` and `agents:write` scopes |
| `turns.py` | The turn context an agent reads before calling its model, and the turn commit written in one transaction |
| `models.py` | Conversations, messages, memories, profile nodes and edges, pending actions |
| `jobs.py` | The prune job |

## Surface

- Routes: `/api/agents`, no module switch. Agent routes take a machine token with `agents:read` or `agents:write` and act on the token's org; `/<org_prefix>/me` routes take a member's Discord session. Officers have no route to agent data.
- Jobs: `agents.prune`, cron `15 4 * * *` (idle conversations after `AGENT_RETENTION_DAYS`, expired memories, old pending actions).
- Tools: none.
- Tables: `agent_conversations`, `agent_messages`, `agent_memories`, `agent_profile_nodes`, `agent_profile_edges`, `agent_pending_actions`.

## More

[docs/agents.md](../../docs/agents.md)
