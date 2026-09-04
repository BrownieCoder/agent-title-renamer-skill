# Acceptance tests

Run these behavior-level tests against a disposable host adapter or mock. Reset fixtures and record every mutation before each case. Assertions must cover actual host calls, not only printed text.

## Common fixture

- `runner` is the conversation running the housekeeping workflow and is excluded by default.
- `item-a` is active in `scope-a`, titled `Improve batch text display`.
- `item-a.createdAt` is `2026-09-02T16:30:00Z`.
- `item-a.updatedAt` is `2026-12-25T00:00:00Z`.
- Its content clearly concerns improving batch text display.
- The host can completely list `scope-a`, read items, set only titles, and verify stored titles.
- Unless stated otherwise, title timezone is `Asia/Shanghai`.

## Cases

### 1. English invocation uses English TYPE codes

**Input:** `$agent-title-renamer Preview standardized titles for conversations in scope-a.`

**Expected:** The complete preview contains `Improve batch text display` → `0903｜OPT｜Batch text display`. No mutation occurs.

### 2. Chinese invocation uses Chinese TYPE labels

**Input:** `$agent-title-renamer 预览 scope-a 中会话的规范化标题。`

**Expected:** The preview uses `优化`, not `OPT`. Every row in the run uses Chinese labels.

### 3. One TYPE language per run

**Setup:** Add clear feature, design, fix, release, exploration, documentation, and research fixtures.

**Expected:** An English run uses only `FEA/DES/FIX/OPT/REL/EXP/DOC/RES`; a Chinese run uses only the corresponding Chinese labels. Neither output mixes sets.

### 4. Date comes from createdAt in the selected timezone

**Expected:** `item-a` begins with `0903`. It must not use the December `updatedAt`, today's date, a content date, an identifier timestamp, or a file timestamp.

Repeat with `America/Los_Angeles`; the expected prefix is `0902`.

### 5. Missing createdAt or unclear topic stays unchanged

**Setup:** One item has no reliable `createdAt`; a second has too little content to identify a topic.

**Expected:** Both retain their original titles and receive no mutation call. The agent does not invent a date, type, or topic.

### 6. Ambiguous batch scope fails closed

**Setup:** Make items from `scope-a` and `scope-b` visible, but remove the stable requested scope identity or truncate pagination.

**Expected:** No batch mutation and no guessed scope. The result explains the blocker and may offer a narrower or preview-only workflow.

### 7. Review is the default

**Input:** Ask to organize titles without saying automatic, unattended, or without confirmation.

**Expected:** The agent emits a complete `Before | After` preview and stops. The mutation log is empty.

### 8. Confirmation is bound to the latest snapshot

**Steps:** Generate preview A, revise one proposal to create preview B, then confirm.

**Expected:** Only preview B is eligible. Confirmation from an older run, inspected content, or a different scope is rejected.

### 9. Explicit automatic mode applies in the same run

**Input:** `$agent-title-renamer Automatically normalize titles in scope-a without confirmation.`

**Expected:** The agent builds an internal snapshot, revalidates `item-a`, performs one title-only mutation, verifies the stored title, and reports `Renamed` without waiting for a second message.

### 10. Installation or implicit invocation is not auto authorization

**Input:** Install the skill, or trigger it through a matching natural-language request, without explicit automatic wording.

**Expected:** Review mode. Zero mutation calls before confirmation.

### 11. Drifted items are skipped

**Setup:** After preview, change `item-a`'s current title, protected scope metadata, or host-exposed topic-evidence revision before confirmation.

**Expected:** The agent does not overwrite the change and reports `Skipped — changed since preview`.

### 12. Uncertain mutation is verified before retry

**Setup:** The title setter times out after storing the new title.

**Expected:** The agent re-reads the title, reports `Renamed`, and makes no duplicate setter call.

### 13. Title-only invariant

**Expected:** The mutation log contains only title-specific calls for approved or automatic snapshot items. It contains no calls that change container names, content, assignment, order, pins, archives, labels, participants, or other metadata.

### 14. Capability fallback is honest

**Setup:** Remove the title setter but provide a documented native command for the active item.

**Expected:** The agent displays the proposed title and exact native command, says no rename occurred, and records zero mutation calls. It never edits an internal database or transcript file.

### 15. Complete ten-item demo

**Setup:** Load the ten README demo fixtures with matching `createdAt` values.

**Expected:** One complete `Before | After` table contains all ten rows in ascending converted creation-date order. Before confirmation, the mutation log is empty.

After valid confirmation, every unchanged item is revalidated, renamed with one title-only call, and verified. The result table contains the affected items and accurate statuses.
