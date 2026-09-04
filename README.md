# Agent Title Renamer Skill

**English (default)** | [简体中文](README.zh-CN.md)

[![Agent Skills](https://img.shields.io/badge/standard-Agent%20Skills-6C5CE7)](https://agentskills.io)
[![Codex](https://img.shields.io/badge/Codex-full%20workflow-111111)](https://openai.com/codex/)
[![License: MIT](https://img.shields.io/badge/license-MIT-2EA44F.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/BrownieCoder/agent-title-renamer-skill?style=flat&logo=github&label=Stars)](https://github.com/BrownieCoder/agent-title-renamer-skill/stargazers)

Turn messy AI-agent histories into short, factual, searchable titles.

One portable naming policy for Codex, Claude Code, and other Agent Skills-compatible tools—with a preview-first workflow and one hard boundary: **conversation titles may change; project and workspace names never do.**

> The skill instructions are portable. Automatic history access and renaming depend on the tools exposed by each host. See [Compatibility](#compatibility) for the exact support level.

[See the 10-title demo](#see-the-difference) · [Install](#install) · [Compatibility](#compatibility) · [Automation](docs/automation.md)

## See the difference

Default format: `MMDD｜TYPE｜Topic`

Here is a complete ten-item preview. Nothing has been renamed yet.

| Before | After |
| --- | --- |
| Fix image upload crash | 0818｜FIX｜Image upload crash |
| Speed up search indexing | 0820｜OPT｜Search indexing |
| Add bulk export | 0822｜FEA｜Bulk export |
| Document API auth | 0824｜DOC｜API authentication |
| Explore offline sync | 0826｜EXP｜Offline sync |
| Prepare v1.2 release | 0828｜REL｜v1.2 release |
| Research vector database options | 0830｜RES｜Vector database options |
| Review UI alignment options | 0901｜DES｜UI alignment check |
| Fix timeout login redirect | 0902｜FIX｜Login redirect |
| Improve batch text display | 0903｜OPT｜Batch text display |

If the preview is correct, reply with an explicit confirmation in the same conversation—for example, `Confirm`. The agent rechecks that exact snapshot, changes titles only, and verifies each result.

| Before | After | Result |
| --- | --- | --- |
| Fix image upload crash | 0818｜FIX｜Image upload crash | Renamed |
| Research vector database options | 0830｜RES｜Vector database options | Renamed |
| Improve batch text display | 0903｜OPT｜Batch text display | Renamed |

Prefer Chinese labels? Invoke the skill in Chinese:

| Before | After |
| --- | --- |
| 优化批次文字显示 | 0903｜优化｜批次文字显示 |
| 修复超时后的登录跳转 | 0902｜修复｜登录跳转 |
| 研究向量数据库选型 | 0830｜研究｜向量数据库选型 |

Each run uses one TYPE language. It never mixes `OPT` and `优化` in the same preview.

## Why it is useful

- **Find old work faster.** Dates, intent, and topic are visible in the sidebar.
- **Preview before changing anything.** Review mode is the default.
- **Use it across agents.** The skill follows the open `SKILL.md` format.
- **Stay in control.** Automatic mode exists only when you explicitly request it.
- **No storage hacks.** The skill never directly edits undocumented internal databases or transcript files.

## Compatibility

The Agent Skills standard defines how instructions are packaged. It does not define a universal conversation API.

| Host | What works in this release |
| --- | --- |
| Codex with task-management tools | Full batch workflow: list, inspect, preview, rename, and verify. |
| Claude Code, skill only | Naming policy and preview generation. For the active session, use the proposed title with Claude Code's native `/rename`; full-history batch mutation is not claimed. |
| Other Agent Skills clients | The naming policy is portable. Preview and apply capabilities adapt to the host's documented title tools. |

This repository does not currently bundle and test a Claude Agent SDK adapter, so it does not support automatic Claude-wide batch renaming.

## Install

### Codex

Ask Codex:

```text
$skill-installer Install the skill from https://github.com/BrownieCoder/agent-title-renamer-skill/tree/main/skills/agent-title-renamer
```

Then invoke it explicitly:

```text
$agent-title-renamer Preview standardized titles for conversations in the current project.
```

### Claude Code

Clone the repository, then copy `skills/agent-title-renamer` to either:

```text
~/.claude/skills/agent-title-renamer          # personal
.claude/skills/agent-title-renamer            # project-local
```

Invoke it with:

```text
/agent-title-renamer Preview a standardized title for this session.
```

Claude Code can rename the active session with `/rename <title>`. The skill will not directly edit Claude's internal JSONL files.

If the host does not expose a reliable session creation timestamp, the skill will not invent the `MMDD` prefix; it will keep the title unchanged or provide undated naming guidance only.

### Other compatible agents

Copy the `skills/agent-title-renamer` directory into that host's Agent Skills directory. Installation paths and invocation syntax vary by product.

Installing the skill only makes it available. It does not scan conversations, rename anything, or create an automation by itself.

The repository and display name include **Skill** for clarity and discovery. The invocation stays shorter: `agent-title-renamer`.

### Upgrading from the Codex-only version

Install `agent-title-renamer`, update saved prompts from `$codex-task-title-renamer` to `$agent-title-renamer`, and test one preview before removing the old skill folder. Repository redirects do not translate skill invocation names.

## How it works

```mermaid
flowchart LR
    A[Resolve host capabilities] --> B[Select exact scope]
    B --> C[Read createdAt and topic]
    C --> D[Build Before / After preview]
    D --> E{Mode}
    E -->|Review, default| F[Wait for confirmation]
    E -->|Explicit auto| G[Revalidate snapshot]
    F --> G
    G --> H[Change titles only]
    H --> I[Verify results]
```

The skill selects the workflow supported by the host:

1. **Full workflow:** the host can list, read, and rename title-bearing items.
2. **Current-item workflow:** the host exposes only the active conversation.
3. **Preview-only workflow:** the host cannot mutate titles; the skill provides exact suggestions or native commands without claiming a rename occurred.

## Naming rules

- Date comes only from `createdAt`, never `updatedAt`.
- An explicit title timezone wins. Otherwise the automation timezone, then the host's configured local timezone, is used.
- Topic describes the actual conversation and does not repeat its project or workspace name.
- Unclear topics keep their original titles. The skill does not guess.
- Titles stay short enough to scan in a sidebar.
- Only title-specific mutation is allowed. Content, assignment, order, pin state, and archive state remain untouched.

| Code | Chinese | Meaning |
| --- | --- | --- |
| FEA | 功能 | Feature |
| DES | 设计 | Design |
| FIX | 修复 | Bug fix |
| OPT | 优化 | Optimization |
| REL | 发布 | Release |
| EXP | 探索 | Exploration |
| DOC | 文档 | Documentation |
| RES | 研究 | Research |

## Review or automatic mode

Review mode is the default: preview first, then confirm that exact snapshot.

Automatic mode is opt-in. Say `automatic`, `unattended`, or `without confirmation` in the request or saved automation prompt. The permission applies only to that run and scope; it does not silently become a global preference.

For recurring housekeeping, see the [automation guide](docs/automation.md). It includes review and explicit automatic templates, with a user-selected schedule and timezone.

## Design boundary

This is a title-governance skill, not a database migration tool. It uses documented host capabilities only. If a host cannot provide a stable item identifier, a reliable `createdAt`, a complete requested scope, or a title-only mutation, the skill stops or falls back to preview-only mode.

The host capability contract is documented in [`references/host-contract.md`](skills/agent-title-renamer/references/host-contract.md).

## Documentation and sources

- [Automation guide](docs/automation.md)
- [Acceptance scenarios](tests/acceptance.md)
- [Agent Skills specification](https://agentskills.io/specification)
- [Claude Code skills](https://code.claude.com/docs/en/slash-commands) and [session naming](https://code.claude.com/docs/en/sessions)
- [Claude Agent SDK session APIs](https://code.claude.com/docs/en/agent-sdk/python)
- [Codex App Server](https://learn.chatgpt.com/docs/app-server)

## Support the project

If cleaner conversation history saves you time, [star the repository](https://github.com/BrownieCoder/agent-title-renamer-skill) so more agent users can find it. Found an edge case or want to contribute a host adapter? [Open an issue](https://github.com/BrownieCoder/agent-title-renamer-skill/issues).

## License

[MIT](LICENSE)

This is an independent community project. It is not an official OpenAI or Anthropic product.
