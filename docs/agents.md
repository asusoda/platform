# Agents module

Storage for AI agents that talk to members (Sparky first): conversations, memories, a profile graph
and pending actions that wait for the member to confirm. The agent keeps no database of its own.
The semantics follow SparkyAI's stores so its engine can call this API instead.

## Who can see what

- An agent calls with a machine token (`kind: agent`) holding `agents:read` and/or `agents:write`.
  The org is the token's. The agent names the member by Discord id in the path.
- A member signed in with Discord sees and deletes their own data at `/api/agents/<org>/me`.
- Officers and superadmins have no route to read agent data. Roles come from the platform
  (Discord roles, officer checks), never from what an agent says.
- Orgs never share rows: the same Discord id in two orgs is two separate members.

## Agent routes

All under `/api/agents/members/<discord_id>`.

| Method and path | Scope | Does |
|---|---|---|
| `PUT /conversations/<uuid>` | write | Create, or confirm ownership. Body `channel_id`, `visibility` (public, private). 409 if another member, channel or visibility holds the id |
| `GET /conversations/<uuid>?visibility=` | read | `{"owned": bool}` |
| `GET /conversations/<uuid>/messages?limit=` | read | Newest summary, then up to `limit` messages after what it covers, oldest first |
| `POST /conversations/<uuid>/messages` | write | Append `messages: [{role, content}]` in one transaction. Returns their `seqs` |
| `POST /conversations/<uuid>/summary` | write | `content`, `covers` (the last seq it stands in for) |
| `GET /channels/<channel>/latest?visibility=` | read | Most recently updated open conversation |
| `POST /channels/<channel>/end` | write | End open conversations in the channel |
| `GET /memories?kinds=&limit=` | read | Unexpired memories, most confident first |
| `POST /memories` | write | `kind` (episodic, semantic, profile, task), `content`, `sensitivity`, `confidence`, `source_seq`, `expires_in_days` |
| `DELETE /memories/<id>` | write | Delete one |
| `GET /profile` | read | Nodes and relations |
| `POST /profile/facts` | write | `facts: [{subject: {kind, label}, relation, object: {kind, label}, confidence}]`. Existing rows keep the higher confidence |
| `GET /profile/matching?subject=&relation=` | read | Relations from a subject, case-insensitive |
| `DELETE /profile/relations` | write | Body `subject`, `relation`, `object` |
| `DELETE /profile/nodes?label=` | write | Delete nodes with that label and their edges |
| `DELETE /data` | write | Forget the member: profile graph and memories |
| `PUT /pending/<uuid>` | write | Hold an action: `action`, `payload_hash`, `ttl_seconds` (default 600) |
| `POST /pending/<uuid>/claim` | write | `approved: bool`. Returns the action once; 404 if unknown, expired, answered or another member's |

## Turns

An agent makes two calls per turn, both under `/api/agents/members/<discord_id>/turn`. Both check
with Discord that the member is in the org's server: 403 when not, 503 when Discord is not
configured or not reachable.

| Method and path | Scope | Does |
|---|---|---|
| `POST /context` | read | Body `conversation_id`, `visibility`, optional `message_limit` (50), `memory_kinds`, `memory_limit` (20), `profile_limit` (100); 0 leaves a part out. Returns `member` (display name, role ids, officer, from Discord), `conversation` (`owned`), `messages`, `memories`, `profile` |
| `POST /commit` | write | Body `conversation_id`, `channel_id`, `visibility`, and any of `messages`, `summary` (`content`, `covers`), `memories`, `facts`, `pending` (`token`, `action`, `payload_hash`, `ttl_seconds`), each shaped as in the routes above. One transaction: when any part is invalid nothing is written. 201 with `seqs`, `summary_seq`, `memory_ids`, `facts`, `pending` |

The per-part routes above stay for agents that write as they go.

## Privacy defaults

- Sensitive memories are encrypted with `SECRETS_KEY` (the same keys as org secrets). Without it they
  cannot be written (503) and existing ones are left out of reads.
- The `agents.prune` job deletes conversations not updated in `AGENT_RETENTION_DAYS` (default 180),
  expired memories, and pending actions a day past expiry.
- Per-turn writes are not in the audit log; deletes and confirmations are.

## Not here yet

- Profile nodes match by exact kind and label. Sparky also merges near-duplicate labels by embedding;
  that waits for the knowledge module (pgvector).
- The member routes need a Discord session with `discord_id`; the web app's member login does not
  set it yet.
