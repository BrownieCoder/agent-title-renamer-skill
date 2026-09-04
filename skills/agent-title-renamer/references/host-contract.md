# Host capability contract

The naming policy is portable; title management comes from the host. Map product-specific concepts to this contract before attempting mutation.

## Capability tiers

### Full workflow

The host must support equivalents of:

```text
listItems(scope, cursor) -> items, nextCursor
readItem(itemId) -> metadata and conversation content
setTitle(itemId, exactTitle) -> result
```

`listItems` must support complete pagination for the requested scope. `readItem` must return current state for revalidation. `setTitle` must change only the visible item title.

Required stable fields:

```text
itemId
currentTitle
createdAt
scopeId
```

Useful optional fields:

```text
hostId
kind
archiveState
updatedAt
```

`updatedAt` may be checked for drift but must never supply the `MMDD` date.

### Current-item workflow

Use when the host can expose metadata and content for only the active conversation. Never imply that other history was inspected.

### Preview-only workflow

Use when title mutation is missing or when the host cannot provide reliable `createdAt` for the inventory as a whole. Generate only what the available evidence supports. If `createdAt` is missing for only a few items, skip those items and continue with supported ones. If the host documents a native user command, show it; do not claim to have executed it.

## Product mappings

| Generic term | Codex example | Claude Code example |
| --- | --- | --- |
| item | task or thread | session |
| scope | project or projectless list | project directory |
| item ID | thread ID | session ID |
| title mutation | native task-title setter | `/rename` for the active session, or `rename_session` through the bundled SDK adapter |

Claude Code's interactive `/rename` is a user-facing command for the current session, not a universal batch API. The bundled Beta adapter maps a guarded, explicitly selected-ID workflow to the documented Python Agent SDK:

```text
listItems      -> list_sessions with one exact directory and no worktree expansion
readItem       -> exact list_sessions re-read + get_session_messages
setTitle       -> rename_session
verify         -> exact list_sessions re-read and custom_title comparison
```

The SDK can omit or deduplicate records before returning them, so this mapping does not prove a complete physical project inventory and must not be presented as one. It covers selected, SDK-visible, locally persisted Claude Code sessions only. It does not provide access to Claude.ai, web, mobile, or another computer's history. The adapter must never parse or modify Claude's internal JSONL transcript format directly.

## Fail-closed rules

Do not batch-mutate when any of these is true:

- scope identity is ambiguous;
- pagination is incomplete;
- `itemId` is unstable or missing;
- `createdAt` is absent or unreliable across the inventory rather than only on isolated skippable items;
- there is no title-only setter;
- revalidation cannot detect drift;
- verification cannot read the final title.

Narrow to a supported scope or fall back to preview-only behavior instead.
