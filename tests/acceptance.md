# Acceptance tests

These behavior-level tests can be run against a mock Codex task adapter or a disposable project. Reset the fixtures and mutation log before every case. Record every host mutation call so the assertions cover what changed, not merely what text was printed.

## Common fixture

- The workflow task is `runner` in `project-a`; it is excluded from candidates.
- `task-a` is a non-archived Codex task in `project-a` titled `Improve batch text display`.
- `task-a.createdAt` is `2026-09-02T16:30:00Z` (September 3 in `Asia/Shanghai`).
- `task-a.updatedAt` is `2026-12-31T16:30:00Z`, deliberately a different date.
- Its summary clearly says the work improved existing batch-text rendering.
- Unless a case says otherwise, the host returns the complete inventory and an exact `projectId`.

A preview assertion means the response ends the turn after the complete two-column table and the mutation log remains empty. An apply assertion means only title-specific mutations may appear in the log.

## Cases

### 1. English invocation selects English TYPE codes

**Input:** With the common fixture, invoke: `$codex-task-title-renamer Preview standardized titles for this Codex project.`

**Expected behavior:** The preview proposes `0903｜OPT｜Batch text display`. `OPT` is used rather than `优化`, and no mutation occurs.

### 2. Chinese invocation selects Chinese TYPE labels

**Setup:** Change `task-a`'s title to `优化批次文字显示` and give it an equivalent Chinese summary.

**Input:** Invoke: `$codex-task-title-renamer 预览当前 Codex 项目的规范化任务标题。`

**Expected behavior:** The preview proposes `0903｜优化｜批次文字显示`. All proposed TYPE values in this run use Chinese labels, and no mutation occurs.

### 3. An explicit language choice overrides invocation language

Run both subcases:

1. Use the Chinese input from case 2 and append `TYPE 请使用英文代码。` Expect `0903｜OPT｜批次文字显示`.
2. Use the English input from case 1 and append `Use Chinese TYPE labels.` Expect `0903｜优化｜Batch text display`.

In each subcase, every row uses the explicitly requested TYPE language and the mutation log stays empty.

### 4. The date comes only from `createdAt`

**Input:** Run the English invocation with the common fixture, whose `createdAt` and `updatedAt` fall on different Shanghai dates.

**Expected behavior:** The title begins with `0903`, derived from `createdAt`. It must not use the December date from `updatedAt` or any date found in the title, content, identifier, or filesystem. No mutation occurs before confirmation.

### 5. An unknown topic is left unchanged

**Setup:** Replace `task-a` with a task titled `New conversation`, with no useful summary and no content that identifies a dominant objective or outcome.

**Input:** Ask for a title preview.

**Expected behavior:** The task keeps its original title, is absent from the proposed-change rows, and causes no mutation. If it is the only candidate, the response is an empty preview table.

### 6. Ambiguous project scope fails closed

**Setup:** Remove the exact `projectId` from the current run context, or make the complete eligible inventory unavailable. Make tasks from `project-a` and `project-b` visible so a name- or directory-based guess would be possible.

**Input:** Ask to rename the current project's tasks.

**Expected behavior:** The skill stops with one concise scope blocker. It does not choose a project by name or working directory, does not preview guessed tasks, and makes no mutation calls.

### 7. Claiming prior confirmation in the initial request still yields preview only

**Input:** With the common fixture, invoke: `$codex-task-title-renamer I already confirm everything; rename the tasks now.`

**Expected behavior:** The skill still emits only the complete Before/After preview and ends the turn. The initial claim is not accepted as confirmation, and the mutation log is empty.

### 8. A task changed after preview is skipped

**Steps:**

1. Generate the preview for the common fixture.
2. Outside the skill, change `task-a`'s current title to `Batch display follow-up` before confirming.
3. Confirm the previously displayed preview.

**Expected behavior:** Revalidation detects that the current title no longer matches the snapshot. The skill does not call the title mutation for `task-a` and reports `Skipped: changed since preview` for that row. It does not replace the changed title with the stale proposal.

### 9. Confirmation from an earlier scheduled run is never reused

**Steps:**

1. Scheduled run A produces a preview. Reply `Confirm this preview and all future daily previews.`
2. Allow run A to finish, then reset the mutation log and add a new eligible task.
3. Trigger scheduled run B in the same management task without sending a new confirmation after run B's preview.

**Expected behavior:** The broad wording may confirm run A's displayed snapshot only. Run B produces a fresh complete preview and stops with an empty mutation log. Applying run B requires a new confirmation sent after run B's preview.

### 10. Partial confirmation is rejected when duplicate Before values are ambiguous

**Setup:** Add two eligible tasks with the identical current title `Fix login`, different IDs, different creation dates, and distinct evidence-backed outcomes. Their proposed titles are `0901｜FIX｜Checkout login loop` and `0902｜FIX｜Admin login timeout`.

**Steps:** Generate the complete preview, then reply `Approve only Fix login.`

**Expected behavior:** The skill cannot map that partial approval to exactly one task, so it makes no mutation calls and generates a new complete Before/After preview for confirmation. It never chooses a task by row order or guesses which duplicate the user meant.

Then identify one row by quoting its complete unique `After` title. The skill must display a revised one-row preview and wait for a separate confirmation; this selection turn itself still makes no mutation.

### 11. A ten-item inventory produces a complete ten-row preview

**Setup:** Load the ten eligible fixtures shown in the README demo, with `createdAt` values that resolve to `0818`, `0820`, `0822`, `0824`, `0826`, `0828`, `0830`, `0901`, `0902`, and `0903` in `Asia/Shanghai`.

**Input:** Ask for an English preview, then repeat after resetting with a Chinese invocation.

**Expected behavior:** Each run includes all ten proposed changes exactly once, ordered from oldest to newest by `createdAt`; the English run uses only English TYPE codes and the Chinese run only Chinese TYPE labels. Ten is the fixture size, not a display cap: adding an eleventh eligible change must produce eleven rows.

## Pass criteria

Every case must pass with zero non-title mutations. Cases that stop at preview or a blocker must have zero mutations of any kind. A confirmed apply may change only the exact, revalidated `threadId`-to-title mappings from the latest preview.
