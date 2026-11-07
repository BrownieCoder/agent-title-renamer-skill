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

**Setup:** Add clear feature, design, fix, release, exploration, documentation, research, independent review, dedicated validation, and configuration fixtures.

**Expected:** An English run uses only `FEA/DES/FIX/OPT/REL/EXP/DOC/RES/REV/TST/CFG`; a Chinese run uses only the corresponding Chinese labels. Neither output mixes sets. The adapter supports preview, one title-only write, and read-back verification for each new type in both languages, and rejects the opposite language before any write.

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

### 16. Topic follows each conversation's language

**Setup:** An English invocation selects one Chinese conversation and one English conversation.

**Expected:** Both TYPE values use English codes, but each Topic keeps that conversation's main language unless the user explicitly requests translation.

### 17. Accurate titles are stable

**Setup:** An item has a compliant, accurate title and receives a routine follow-up or scheduler wakeup.

**Expected:** No proposal or mutation. Adding the three new types does not by itself cause retagging.

### 18. Dedicated categories follow the main deliverable

**Setup:** Compare an independent code review, a reproduction-only task, environment setup, and a feature implemented with tests and review.

**Expected:** Use REV/评审, TST/测试, CFG/配置, and FEA/功能 respectively. Supporting checks do not replace a feature's primary TYPE.

### 19. Legacy project evidence is retained and revalidated

**Setup:** A complete native host inventory contains an item with null project metadata. Conversation evidence explicitly identifies a repository in the accessible project list. Another item has only a matching cwd or similar project name.

**Expected:** The first may be classified under the resolved project while retaining raw metadata and concrete evidence for revalidation. The second stays unchanged. Changed raw metadata, resolved project, or evidence prevents apply. Neither path changes membership or accesses private app storage. The Claude adapter still refuses to expand its exact-directory scope.

### 20. First-turn naming is explicitly enabled and scoped

**Setup:** User-controlled host instructions explicitly authorize current-conversation naming with a selected title timezone. The first request has a clear objective and the host provides reliable createdAt, a native setter, and verification.

**Expected:** One verified title-only rename for the current user-owned conversation, without a second confirmation. No scan of unrelated history, new conversation, or rename of internal subagent sessions. A later preview-only request still produces zero writes.

### 21. First-turn capability failure does not block the user's work

**Setup:** Enable first-turn naming but remove reliable createdAt, title mutation, or read-back capability.

**Expected:** Keep the original title and continue the requested work. Do not invent the date, edit storage, or claim a rename. Installing the skill alone never enables first-turn naming or persistent automatic authorization.

## Executable Claude adapter coverage

Run the mock-backed suite without touching real Claude history:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The suite verifies zero-write previews, inspection-bound proposals, `created_at` date enforcement, single-language TYPE validation, selected-ID directory scoping, oversized-session refusal, sealed-plan permissions and digests, default current-session exclusion, metadata and message drift skips, automatic-mode double authorization, one title-only call per success, and verification after an uncertain write.
