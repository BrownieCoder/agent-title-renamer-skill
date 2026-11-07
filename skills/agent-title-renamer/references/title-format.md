# Title Format

Read before proposing standardized titles in any supported host.

## Choose title language and timezone

### TYPE language

Use one TYPE language for the entire run:

1. Follow an explicit language request.
2. Otherwise, use Chinese labels when the invocation is primarily Chinese.
3. Use English codes for English or ambiguous invocations.

Never mix English codes and Chinese labels in one run.

| English | Chinese | Meaning |
| --- | --- | --- |
| FEA | 功能 | feature |
| DES | 设计 | design or implementation plan |
| FIX | 修复 | bug fix |
| OPT | 优化 | optimization |
| REL | 发布 | release |
| EXP | 探索 | exploration |
| DOC | 文档 | documentation |
| RES | 研究 | research |
| REV | 评审 | independent review |
| TST | 测试 | dedicated validation or reproduction |
| CFG | 配置 | environment, installation, or tool setup |

### Title timezone

Choose the timezone in this order:

1. A timezone explicitly selected by the user for title dates.
2. The timezone saved in the current automation prompt.
3. The host's configured local IANA timezone.

If none is available, ask for a timezone before proposing dated titles. Do not silently assume `Asia/Shanghai` or UTC.

## Build each title

Use exactly:

```text
MMDD｜TYPE｜Topic
```

### Date

- Read the item's `createdAt` metadata.
- Convert `createdAt` to the chosen title timezone, then format it as `MMDD`.
- Never use `updatedAt`, last activity, file timestamps, identifier timestamps, a date mentioned in content, or today's date as a substitute.
- If reliable `createdAt` is unavailable for one item, keep that item's original title and continue with other supported items. If the host cannot provide reliable `createdAt` for the inventory as a whole, do not batch-mutate. Do not invent the date.

### TYPE

- Classify the item's primary completed or intended work, not a passing remark.
- Use exactly one value from the table above.
- Prefer the dominant outcome when an item touches multiple types.
- Use `REV / 评审` when evaluating an existing change or proposal is the deliverable; `TST / 测试` when validation or reproduction is the deliverable; and `CFG / 配置` for environment, installation, or tool settings.
- Tests and reviews that accompany a feature or fix do not replace that implementation's TYPE. Use `RES / 研究` for evidence gathering and comparison, `EXP / 探索` for open-ended possibilities, and `DES / 设计` for a concrete design or implementation plan.
- If no type is supportable from the content, keep the original title.

### Topic

- Summarize what the item is actually about.
- Write Topic in the item's main language unless the user explicitly chooses another language. TYPE language is selected for the whole run; Topic language may differ between items. Preserve proper nouns and established technical identifiers in their conventional form.
- Prefer a concrete object or outcome over generic wording such as “discussion,” “help,” or “update.”
- Do not repeat the container name.
- Do not repeat the TYPE meaning without adding a specific subject.
- Preserve established product names, acronyms, versions, and technical identifiers.
- Keep it short and sidebar-friendly.
- If the topic is unclear, keep the original title. Do not guess.
- Do not include credentials, sensitive personal details, or private identifiers in a sidebar title.

## Preserve accurate titles

Keep an already compliant, accurate title, including titles using the original eight types. Do not retag an item merely because more types are now available. Change TYPE or Topic only when the main objective or substantial outcome has changed; routine follow-ups and scheduler wakeups do not justify renaming.
