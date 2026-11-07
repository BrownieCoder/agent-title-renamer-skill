# Automation guide for Agent Title Renamer Skill

[中文](automation.zh-CN.md)

Installing Agent Title Renamer Skill does not create a schedule or run it automatically. Automation is a separate host feature, and title mutation is available only when that host exposes the required conversation tools.

## Choose three things first

Before creating an automation, choose:

1. **Scope:** current project, selected projects, or all accessible projects.
2. **Schedule and timezone:** for example, twice daily at 09:00 and 21:00 in a timezone you select.
3. **Mode:** review or automatic. Also choose one TYPE language for the run; the [11 types](../README.md#naming-rules) include review (`REV`), testing (`TST`), and configuration (`CFG`).

The schedule timezone controls when the automation runs. The title timezone controls how `createdAt` becomes `MMDD`. They may be the same, but state both explicitly.

Event-based “run whenever a new conversation appears” is preferable when a host offers that trigger. Otherwise, use a recurring schedule.

## Review mode template

Use this when you want to approve every batch:

```text
Use $agent-title-renamer to inspect eligible conversations in [EXACT SCOPE].
Use [TITLE TIMEZONE] when converting createdAt to MMDD.
Use [TYPE LANGUAGE] for TYPE; keep each Topic in that conversation's main language.
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
Use [TYPE LANGUAGE] for TYPE; keep each Topic in that conversation's main language.
Keep already compliant, accurate titles. Revalidate every item, make at most one title-setter call per item, and verify every result.
Report verified changes, new skips, or failures; remain quiet when nothing actionable changes.
Never bypass host permission prompts or access controls.
Never rename a project or workspace. Never change content, assignment, order, pin state, or archive state.
```

Keep the scope exact. “All projects” should be used only when the host can enumerate the full set safely and that breadth is intentional.

For legacy items with null project metadata, use documented host records or concrete conversation evidence, such as a repository URL, artifact path, or recorded migration, tied to one accessible project. A matching name or working directory alone is not enough. Preserve the raw metadata and evidence for revalidation, leave ambiguous or truly projectless items unchanged, and never change membership. This does not expand the Claude adapter's selected-ID, exact-directory boundary or permit reading private app storage.

## Name new conversations during the first turn

Recurring cleanup and first-turn naming are separate options. If you explicitly want the current conversation named when work starts, add a scoped rule to the host's instruction file: `~/.codex/AGENTS.md` for Codex, or `~/.claude/CLAUDE.md` for Claude Code. Merge it with existing instructions; installing the skill does not edit these files. See the official [Codex instruction guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md) and [Claude Code instruction guide](https://code.claude.com/docs/en/memory).

Choose an IANA title timezone and replace `[TITLE TIMEZONE]` before enabling this example:

```text
For new user-owned conversations, I authorize automatic title-only naming of the current conversation during its first turn, once the request is clear. This standing authorization applies only to the current conversation until I revoke it.
Use the installed agent-title-renamer skill's MMDD｜TYPE｜Topic policy and 11 types. Use Chinese TYPE labels for Chinese requests and English codes otherwise, unless I explicitly choose a language. Topic follows the conversation's main language.
Read verified createdAt and convert it to [TITLE TIMEZONE]; never use updatedAt, today's date, or a date already in the title.
Keep accurate, compliant titles. Change them only for a material change in the main goal, not on routine follow-ups.
Use a documented title setter. Recheck identity, scope, createdAt, current title, and topic evidence before one write, then read back to verify.
Do not scan other conversations, create a new conversation, apply this rule to internal subagent sessions, or change any project name or other metadata.
If the host cannot provide reliable creation metadata, a title setter, or read-back verification, keep the title and continue the user's work. An explicit preview-only request takes precedence.
```

This asks the assistant to name the conversation when it first handles the request; it does not promise to replace the app's initial placeholder before that turn runs. Instruction changes must be loaded by the host. In Claude Code, `/rename` is the current-session fallback; when it is only a user-facing command, provide the suggestion instead of claiming an automatic rename. The SDK bridge still needs explicit current-session inclusion and all of its usual snapshot and size checks; active-session drift is a reason to skip, not relax the checks.

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
