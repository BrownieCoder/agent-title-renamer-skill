# Automation guide for Agent Title Renamer Skill

[中文](automation.zh-CN.md)

Installing Agent Title Renamer Skill does not create a schedule or run it automatically. Automation is a separate host feature, and title mutation is available only when that host exposes the required conversation tools.

## Choose three things first

Before creating an automation, choose:

1. **Scope:** current project, selected projects, or all accessible projects.
2. **Schedule and timezone:** for example, twice daily at 09:00 and 21:00 in a timezone you select.
3. **Mode:** review or automatic.

The schedule timezone controls when the automation runs. The title timezone controls how `createdAt` becomes `MMDD`. They may be the same, but state both explicitly.

Event-based “run whenever a new conversation appears” is preferable when a host offers that trigger. Otherwise, use a recurring schedule.

## Review mode template

Use this when you want to approve every batch:

```text
Use $agent-title-renamer to inspect eligible conversations in [EXACT SCOPE].
Use [TITLE TIMEZONE] when converting createdAt to MMDD.
Generate the complete Before/After preview in review mode, then stop.
Never rename a project or workspace, and change no conversation property other than title.
```

The preview appears in the task or run surfaced by the host. Open that same conversation and reply with an explicit confirmation—for example, `Confirm`. Each scheduled run produces its own snapshot.

## Automatic mode template

Use this only when you want unattended title changes:

```text
Use $agent-title-renamer in automatic mode for [EXACT SCOPE].
This saved prompt explicitly authorizes this run to apply title changes without a separate confirmation.
Use [TITLE TIMEZONE] when converting createdAt to MMDD.
Revalidate every item, change titles only, verify every result, and report changed, skipped, or failed items.
Never bypass host permission prompts or access controls.
Never rename a project or workspace. Never change content, assignment, order, pin state, or archive state.
```

Keep the scope exact. “All projects” should be used only when the host can enumerate the full set safely and that breadth is intentional.

## Codex scheduled tasks

In Codex, ask for an automation in natural language and let the user choose the schedule timezone. Example:

```text
Create a recurring automation for Agent Title Renamer Skill. Ask me to choose the days, times, and timezone before creating it. Also ask which timezone should be used for title dates.

Use this saved prompt:
[PASTE ONE TEMPLATE FROM ABOVE WITH AN EXACT SCOPE]
```

For project-scoped local work, you may attach the automation to a dedicated housekeeping task such as `Title cleanup`. This keeps previews and confirmations in one place. The computer, Codex app, and local project must be available when a local run fires.

After creation, verify:

- the schedule shows the timezone you selected;
- the saved prompt names `$agent-title-renamer`;
- scope and mode are explicit;
- title timezone is explicit;
- the automation is attached to the intended project or task;
- automatic mode appears only if you deliberately selected it.

## Claude Code

Claude Code can load this skill and generate standardized title proposals. With the optional bundled Python SDK adapter configured, it can also list, revalidate, rename, and verify locally persisted sessions in one exact project directory per run. Cross-project and cross-worktree SDK inventories are read-only discovery, so create separate exact-directory runs instead of one broad mutation plan. Without the adapter, its native `/rename` command remains the current-session fallback.

Claude routines or an external scheduler may replay the saved prompt. Installing the skill or adapter does not create a schedule. For unattended runs, the saved prompt must explicitly authorize automatic mode; the adapter then requires both an automatic sealed plan and the matching apply flag. Prefer completed sessions while the Claude batch bridge is Beta.

This covers local Claude Code history only. It does not reach Claude.ai, web, mobile, another computer, or cloud history that is not persisted locally. Do not automate by editing Claude's internal JSONL files.

## Other Agent Skills hosts

Use the host's own scheduler, hook, routine, or event trigger. Keep the same saved-prompt requirements:

- exact scope;
- schedule timezone;
- title timezone;
- review or explicit automatic mode;
- title-only mutation;
- revalidation and verification.

If the host cannot list, read, rename, and verify the requested items, use preview-only mode.

## Change or stop the automation

Ask the host to show the existing automation before changing it. Update the existing schedule instead of creating a duplicate. Pause or delete it through the host's supported automation controls.
