# Skills for Platform MCP

Skills for agents that use Platform through its MCP server: Hermes, Claude Code, Sparky or any MCP client. Platform MCP is one gateway to an org: its data, activity, members, access, hosting, the services it connected, its modules and the server.

Start with [platform-mcp](platform-mcp/SKILL.md). It says how to connect and which skill to read for a task. Over MCP, the `guide` tool gives the same skills, so an agent that cannot install them still reads them.

| Skill | For |
| --- | --- |
| [platform-mcp](platform-mcp/SKILL.md) | Connect, the tool layers, the modules gateway, confirm, batch and scopes. Read first |
| [platform-search](platform-search/SKILL.md) | Answer questions with `search`: stored pages, live sources, the web |
| [platform-activity](platform-activity/SKILL.md) | Errors, notifications, the audit log, CI runs, and fixing a failed run on GitHub |
| [platform-hosting](platform-hosting/SKILL.md) | Apps: register, deploy, roll back, logs, templates, an app's own MCP tools |
| [platform-access](platform-access/SKILL.md) | Tokens, secrets, webhooks and connections |
| [platform-members](platform-members/SKILL.md) | Members, Discord sync, org settings, and turning modules on and off |
| [platform-server](platform-server/SKILL.md) | The server: status, services, logs, restarts and named commands. Superadmin only |

Each module with tools also has its own skill, which `modules.skill` returns, such as `modules/knowledge/SKILL.md`.

## Install

```bash
hermes skills tap add asusoda/platform     # Hermes: this repo is a tap, skills/ is its path
cp -r skills/platform-* ~/.claude/skills/  # Claude Code, from a clone
```

## Write a skill

One folder per skill with a `SKILL.md`: frontmatter with `name` (the folder name) and `description` (when to use it), then the steps. Keep it short. Name tools as the tool list names them. Add the skill to the table above. `tests/contract/test_guide.py` checks each one.
