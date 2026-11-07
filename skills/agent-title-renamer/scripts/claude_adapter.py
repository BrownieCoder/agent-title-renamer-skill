#!/usr/bin/env python3
"""Safe Claude Code session adapter for Agent Title Renamer Skill.

The adapter deliberately does not decide titles. It exposes documented Claude
Agent SDK session APIs, seals exact rename plans, revalidates them, and verifies
every write.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.metadata
import json
import os
import re
import sys
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SCHEMA_VERSION = 1
ADAPTER_VERSION = "0.1.0-beta"
MINIMUM_SDK_VERSION = "0.1.74"
MAXIMUM_SDK_VERSION_EXCLUSIVE = "0.3.0"
MAX_SAFE_SESSION_BYTES = 2 * 65_536
ENGLISH_TYPES = frozenset(
    {"FEA", "DES", "FIX", "OPT", "REL", "EXP", "DOC", "RES", "REV", "TST", "CFG"}
)
CHINESE_TYPES = frozenset(
    {"功能", "设计", "修复", "优化", "发布", "探索", "文档", "研究", "评审", "测试", "配置"}
)
TITLE_PATTERN = re.compile(r"^([0-9]{4})｜([^｜]+)｜([^｜]+)$")
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class AdapterError(RuntimeError):
    """A safe, user-facing adapter failure."""


def _attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_json_bytes(value)).hexdigest()


def _current_title(info: Any) -> str:
    custom_title = _attr(info, "custom_title")
    summary = _attr(info, "summary")
    title = custom_title if isinstance(custom_title, str) and custom_title else summary
    if not isinstance(title, str) or not title.strip():
        raise AdapterError(
            "Claude returned a session without a readable display title."
        )
    return title


def _canonical_directory(value: str) -> str:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise AdapterError(f"Project directory does not exist: {path}")
    return str(path)


def _scope_from_args(args: argparse.Namespace) -> dict[str, Any]:
    excluded = set(getattr(args, "exclude_session", []))
    current_session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    include_current_session = bool(getattr(args, "include_current_session", False))
    if current_session and not include_current_session:
        excluded.add(current_session)
    if getattr(args, "all_projects", False):
        return {
            "kind": "all_projects",
            "include_worktrees": bool(args.include_worktrees),
            "include_current_session": include_current_session,
            "excluded_session_ids": sorted(excluded),
        }
    directory = getattr(args, "directory", None)
    if directory:
        return {
            "kind": "directory",
            "directory": _canonical_directory(directory),
            "include_worktrees": bool(args.include_worktrees),
            "include_current_session": include_current_session,
            "excluded_session_ids": sorted(excluded),
        }
    raise AdapterError("Choose exactly one scope: --directory PATH or --all-projects.")


def _scope_directory(scope: Mapping[str, Any]) -> str | None:
    if not isinstance(scope, Mapping):
        raise AdapterError("The plan has an invalid scope object.")
    if scope.get("kind") == "directory":
        directory = scope.get("directory")
        if not isinstance(directory, str) or not directory:
            raise AdapterError("The plan has an invalid directory scope.")
        return directory
    if scope.get("kind") == "all_projects":
        return None
    raise AdapterError("The plan has an unsupported scope.")


def _list_sessions(sdk: Any, scope: Mapping[str, Any]) -> list[Any]:
    return list(
        sdk.list_sessions(
            directory=_scope_directory(scope),
            limit=None,
            offset=0,
            include_worktrees=bool(scope.get("include_worktrees", True)),
        )
    )


def _exact_listed_info(
    sdk: Any, scope: Mapping[str, Any], session_id: str
) -> Any | None:
    if scope.get("kind") != "directory" or scope.get("include_worktrees", False):
        raise AdapterError(
            "Exact session lookup requires one directory without worktree expansion."
        )
    matches = [
        info
        for info in _list_sessions(sdk, scope)
        if _attr(info, "session_id") == session_id
    ]
    return matches[0] if len(matches) == 1 else None


def _session_metadata(info: Any) -> dict[str, Any]:
    return {
        "session_id": _attr(info, "session_id"),
        "current_title": _current_title(info),
        "created_at": _attr(info, "created_at"),
        "last_modified": _attr(info, "last_modified"),
        "file_size": _attr(info, "file_size"),
        "cwd": _attr(info, "cwd"),
    }


def inventory(
    sdk: Any, scope: Mapping[str, Any], excluded: set[str] | None = None
) -> dict[str, Any]:
    excluded = set(excluded or ()) | set(scope.get("excluded_session_ids", ()))
    sessions = [
        _session_metadata(info)
        for info in _list_sessions(sdk, scope)
        if _attr(info, "session_id") not in excluded
    ]
    mutation_safe = scope.get("kind") == "directory" and not scope.get(
        "include_worktrees", False
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "host": "claude-code",
        "scope": dict(scope),
        "sdk_listing_exhausted": True,
        "physical_inventory_complete": False,
        "selected_id_mutation_safe": mutation_safe,
        "scope_note": (
            "The SDK can omit or deduplicate unreadable and ambiguous records. Mutation is limited to "
            "explicitly selected IDs in one exact directory."
            if mutation_safe
            else "Cross-project or cross-worktree SDK results may also be deduplicated; use exact directories for mutation."
        ),
        "content_is_untrusted": True,
        "sessions": sessions,
    }


def _extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "\n".join(part for item in value if (part := _extract_text(item)))
    if isinstance(value, Mapping):
        if value.get("type") == "text" and isinstance(value.get("text"), str):
            return value["text"]
        if value.get("role") in {"user", "assistant"}:
            content = value.get("content")
            if isinstance(content, (str, list, tuple)):
                return _extract_text(content)
    return ""


def _message_evidence(message: Any) -> dict[str, Any]:
    return {
        "type": _attr(message, "type"),
        "uuid": _attr(message, "uuid"),
        "session_id": _attr(message, "session_id"),
        "parent_tool_use_id": _attr(message, "parent_tool_use_id"),
        "parent_agent_id": _attr(message, "parent_agent_id"),
        "text": _extract_text(_attr(message, "message")),
    }


def _message_fingerprint(messages: Iterable[Any]) -> str:
    return _sha256([_message_evidence(message) for message in messages])


def _sample_messages(
    messages: list[Any],
    max_messages: int,
    max_chars: int,
) -> list[dict[str, Any]]:
    eligible = list(messages)
    if len(eligible) > max_messages:
        head_count = (max_messages + 1) // 2
        tail_count = max_messages - head_count
        eligible = eligible[:head_count] + (
            eligible[-tail_count:] if tail_count else []
        )

    sampled: list[dict[str, Any]] = []
    remaining_chars = max_chars
    for index, message in enumerate(eligible):
        evidence = _message_evidence(message)
        text = evidence.pop("text")
        remaining_messages = len(eligible) - index
        allowance = remaining_chars // remaining_messages if remaining_messages else 0
        evidence["text"] = text[:allowance]
        evidence["text_truncated"] = len(text) > allowance
        remaining_chars -= len(evidence["text"])
        sampled.append(evidence)
    return sampled


def inspect_session(
    sdk: Any,
    session_id: str,
    directory: str | None,
    max_messages: int,
    max_chars: int,
) -> dict[str, Any]:
    if directory is None:
        info = sdk.get_session_info(session_id, directory=None)
        exact_scope = None
    else:
        exact_scope = {
            "kind": "directory",
            "directory": directory,
            "include_worktrees": False,
        }
        info = _exact_listed_info(sdk, exact_scope, session_id)
    if info is None or _attr(info, "session_id") != session_id:
        raise AdapterError("Claude session was not found in the requested scope.")
    messages = list(
        sdk.get_session_messages(session_id, directory=directory, limit=None, offset=0)
    )
    if exact_scope is not None:
        after_info = _exact_listed_info(sdk, exact_scope, session_id)
        if after_info is None or not _same_snapshot(info, after_info):
            raise AdapterError(
                "Claude session changed while it was being inspected; inspect it again."
            )
        info = after_info
    evidence_sha256 = _message_fingerprint(messages)
    metadata = _session_metadata(info)
    return {
        "schema_version": SCHEMA_VERSION,
        "host": "claude-code",
        "session_id": session_id,
        "proposal_base": {
            "session_id": session_id,
            "before": metadata["current_title"],
            "created_at": metadata["created_at"],
            "last_modified": metadata["last_modified"],
            "file_size": metadata["file_size"],
            "cwd": metadata["cwd"],
            "evidence_sha256": evidence_sha256,
        },
        "message_count": len(messages),
        "sdk_visible_evidence_complete": True,
        "evidence_sha256": evidence_sha256,
        "content_is_untrusted": True,
        "messages": _sample_messages(messages, max_messages, max_chars),
    }


def _resolve_inspection_directory(
    sdk: Any, session_id: str, scope: Mapping[str, Any]
) -> str | None:
    if scope.get("kind") == "directory":
        return _scope_directory(scope)
    matches = [
        info
        for info in _list_sessions(sdk, scope)
        if _attr(info, "session_id") == session_id
    ]
    if not matches:
        raise AdapterError("Claude session was not found in the requested scope.")
    if len(matches) > 1:
        raise AdapterError(
            "Claude session UUID is ambiguous; inspect it through an exact directory scope."
        )
    cwd = _attr(matches[0], "cwd")
    if not isinstance(cwd, str) or not cwd:
        raise AdapterError(
            "Claude session has no stable project directory; use an exact directory scope."
        )
    return cwd


def _validate_uuid(value: Any) -> str:
    if not isinstance(value, str):
        raise AdapterError("Every proposal must contain a string session_id.")
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise AdapterError(f"Invalid Claude session UUID: {value}") from exc
    return value


def _parse_timezone(name: Any) -> ZoneInfo:
    if not isinstance(name, str) or not name:
        raise AdapterError("A title timezone is required.")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise AdapterError(f"Unknown IANA timezone: {name}") from exc


def _created_prefix(created_at: Any, title_timezone: str) -> str:
    if (
        not isinstance(created_at, int)
        or isinstance(created_at, bool)
        or created_at <= 0
    ):
        raise AdapterError("The session has no reliable created_at timestamp.")
    zone = _parse_timezone(title_timezone)
    created = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).astimezone(
        zone
    )
    return created.strftime("%m%d")


def _validate_title(
    title: Any, created_at: int, title_timezone: str, type_language: str
) -> str:
    if (
        not isinstance(title, str)
        or title != title.strip()
        or "\n" in title
        or "\r" in title
    ):
        raise AdapterError("Every proposed title must be one non-empty, trimmed line.")
    if len(title) > 120:
        raise AdapterError("A proposed title exceeds the 120-character safety limit.")
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in title):
        raise AdapterError(
            "A proposed title contains control or invisible formatting characters."
        )
    match = TITLE_PATTERN.fullmatch(title)
    if not match:
        raise AdapterError(f"Title does not match MMDD｜TYPE｜Topic: {title}")
    date_part, type_part, topic = match.groups()
    expected_date = _created_prefix(created_at, title_timezone)
    if date_part != expected_date:
        raise AdapterError(
            f"Title date {date_part} does not match created_at in {title_timezone} ({expected_date})."
        )
    allowed = ENGLISH_TYPES if type_language == "en" else CHINESE_TYPES
    if type_part not in allowed:
        raise AdapterError(
            f"TYPE {type_part!r} does not match the plan language {type_language!r}."
        )
    if not topic.strip():
        raise AdapterError("A proposed title has an empty topic.")
    return title


PROPOSAL_FIELDS = frozenset(
    {
        "session_id",
        "before",
        "created_at",
        "last_modified",
        "file_size",
        "cwd",
        "evidence_sha256",
        "after",
    }
)


def _validate_proposal(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != PROPOSAL_FIELDS:
        raise AdapterError(
            "Each proposal must contain only session_id, before, created_at, last_modified, "
            "file_size, cwd, evidence_sha256, and after."
        )
    session_id = _validate_uuid(raw["session_id"])
    if not isinstance(raw["before"], str) or not raw["before"]:
        raise AdapterError(f"Proposal has no original title: {session_id}")
    if not isinstance(raw["created_at"], int) or isinstance(raw["created_at"], bool):
        raise AdapterError(f"Proposal has no valid creation time: {session_id}")
    if not isinstance(raw["last_modified"], int) or isinstance(
        raw["last_modified"], bool
    ):
        raise AdapterError(f"Proposal has no valid modification time: {session_id}")
    if not isinstance(raw["file_size"], int) or isinstance(raw["file_size"], bool):
        raise AdapterError(f"Proposal has no valid local file size: {session_id}")
    if raw["file_size"] < 0:
        raise AdapterError(f"Proposal has a negative local file size: {session_id}")
    if raw["cwd"] is not None and not isinstance(raw["cwd"], str):
        raise AdapterError(
            f"Proposal has an invalid recorded working directory: {session_id}"
        )
    if not isinstance(raw["evidence_sha256"], str) or not SHA256_PATTERN.fullmatch(
        raw["evidence_sha256"]
    ):
        raise AdapterError(f"Proposal has no valid evidence fingerprint: {session_id}")
    return dict(raw)


def _load_proposals(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdapterError(f"Cannot read proposals JSON: {exc}") from exc
    if not isinstance(payload, Mapping) or set(payload) != {"items"}:
        raise AdapterError(
            "Proposals must be an object containing only an items array."
        )
    raw_items = payload["items"]
    if not isinstance(raw_items, list) or not raw_items:
        raise AdapterError("Proposals items must be a non-empty array.")
    proposals: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_items:
        proposal = _validate_proposal(raw)
        session_id = proposal["session_id"]
        if session_id in seen:
            raise AdapterError(f"Duplicate session_id in proposals: {session_id}")
        seen.add(session_id)
        proposals.append(proposal)
    return proposals


def _same_snapshot(left: Any, right: Any) -> bool:
    fields = ("session_id", "created_at", "last_modified", "file_size", "cwd")
    return all(
        _attr(left, field) == _attr(right, field) for field in fields
    ) and _current_title(left) == _current_title(right)


def _lookup_directory(info: Any, scope: Mapping[str, Any]) -> str | None:
    if scope.get("kind") == "directory":
        return _scope_directory(scope)
    cwd = _attr(info, "cwd")
    if isinstance(cwd, str) and cwd:
        return cwd
    if scope.get("kind") == "all_projects":
        raise AdapterError(
            "A session in the all-projects scope has no stable project directory; use a narrower scope."
        )
    return _scope_directory(scope)


def build_plan(
    sdk: Any,
    scope: Mapping[str, Any],
    proposals: list[dict[str, Any]],
    title_timezone: str,
    type_language: str,
    mode: str,
) -> dict[str, Any]:
    if scope.get("kind") != "directory" or scope.get("include_worktrees", False):
        raise AdapterError(
            "Claude mutation plans require one exact directory with worktree expansion disabled. "
            "Use cross-project inventory only for read-only discovery, then preview each directory separately."
        )
    _parse_timezone(title_timezone)
    if type_language not in {"en", "zh"}:
        raise AdapterError("TYPE language must be en or zh.")
    if mode not in {"review", "automatic"}:
        raise AdapterError("Mode must be review or automatic.")

    sdk_inventory = _list_sessions(sdk, scope)
    by_id: dict[str, Any] = {}
    duplicate_ids: set[str] = set()
    for info in sdk_inventory:
        session_id = _attr(info, "session_id")
        if session_id in by_id:
            duplicate_ids.add(session_id)
        else:
            by_id[session_id] = info
    excluded = set(scope.get("excluded_session_ids", ()))
    plan_items: list[dict[str, Any]] = []
    seen_proposals: set[str] = set()
    for raw_proposal in proposals:
        proposal = _validate_proposal(raw_proposal)
        session_id = proposal["session_id"]
        if session_id in seen_proposals:
            raise AdapterError(f"Duplicate session_id in proposals: {session_id}")
        seen_proposals.add(session_id)
        if session_id in excluded:
            raise AdapterError(
                f"Proposed session is explicitly excluded from this scope: {session_id}"
            )
        if session_id in duplicate_ids:
            raise AdapterError(
                f"Session UUID is ambiguous across the requested scope; use a narrower directory: {session_id}"
            )
        listed = by_id.get(session_id)
        if listed is None:
            raise AdapterError(
                f"Proposed session is not present in the SDK listing for the requested directory: {session_id}"
            )
        lookup_directory = _lookup_directory(listed, scope)
        before_info = _exact_listed_info(sdk, scope, session_id)
        if before_info is None or not _same_snapshot(listed, before_info):
            raise AdapterError(
                f"Session changed while the preview was being built: {session_id}"
            )
        messages = list(
            sdk.get_session_messages(
                session_id, directory=lookup_directory, limit=None, offset=0
            )
        )
        after_info = _exact_listed_info(sdk, scope, session_id)
        if after_info is None or not _same_snapshot(before_info, after_info):
            raise AdapterError(
                f"Session changed while the preview was being built: {session_id}"
            )

        current_evidence = _message_fingerprint(messages)
        proposal_snapshot = {
            "before": proposal["before"],
            "created_at": proposal["created_at"],
            "last_modified": proposal["last_modified"],
            "file_size": proposal["file_size"],
            "cwd": proposal["cwd"],
            "evidence_sha256": proposal["evidence_sha256"],
        }
        current_snapshot = {
            "before": _current_title(after_info),
            "created_at": _attr(after_info, "created_at"),
            "last_modified": _attr(after_info, "last_modified"),
            "file_size": _attr(after_info, "file_size"),
            "cwd": _attr(after_info, "cwd"),
            "evidence_sha256": current_evidence,
        }
        if proposal_snapshot != current_snapshot:
            raise AdapterError(
                f"Session changed after inspection; inspect it again before previewing: {session_id}"
            )

        file_size = _attr(after_info, "file_size")
        if not isinstance(file_size, int) or isinstance(file_size, bool):
            raise AdapterError(f"Session has no reliable local file size: {session_id}")
        if file_size > MAX_SAFE_SESSION_BYTES:
            raise AdapterError(
                f"Session exceeds the current {MAX_SAFE_SESSION_BYTES}-byte safe metadata window: {session_id}"
            )

        created_at = _attr(after_info, "created_at")
        after = _validate_title(
            proposal["after"], created_at, title_timezone, type_language
        )
        before = _current_title(after_info)
        if before == after:
            raise AdapterError(f"Proposal is not an actual title change: {session_id}")
        plan_items.append(
            {
                "session_id": session_id,
                "lookup_directory": lookup_directory,
                "cwd": _attr(after_info, "cwd"),
                "created_at": created_at,
                "last_modified": _attr(after_info, "last_modified"),
                "file_size": file_size,
                "before": before,
                "after": after,
                "evidence_sha256": current_evidence,
            }
        )

    plan_items.sort(key=lambda item: (item["created_at"], item["session_id"]))
    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "adapter": "claude-agent-sdk",
        "adapter_version": ADAPTER_VERSION,
        "mode": mode,
        "scope": dict(scope),
        "selection_complete": True,
        "title_timezone": title_timezone,
        "type_language": type_language,
        "items": plan_items,
    }
    plan["plan_digest"] = _sha256(plan)
    return plan


def _write_private_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise AdapterError(f"Refusing to overwrite existing plan: {path}") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _load_plan(path: Path) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdapterError(f"Cannot read rename plan: {exc}") from exc
    if not isinstance(plan, dict):
        raise AdapterError("Rename plan must be a JSON object.")
    return plan


def _validate_plan(plan: Mapping[str, Any]) -> str:
    digest = plan.get("plan_digest")
    if not isinstance(digest, str):
        raise AdapterError("Rename plan has no digest.")
    unsigned = dict(plan)
    unsigned.pop("plan_digest", None)
    expected = _sha256(unsigned)
    if digest != expected:
        raise AdapterError("Rename plan digest does not match its contents.")
    if plan.get("schema_version") != SCHEMA_VERSION:
        raise AdapterError("Unsupported rename plan schema version.")
    if plan.get("adapter_version") != ADAPTER_VERSION:
        raise AdapterError("Rename plan was created by an unsupported adapter version.")
    if (
        plan.get("adapter") != "claude-agent-sdk"
        or plan.get("selection_complete") is not True
    ):
        raise AdapterError("Rename plan is not a complete selected-ID Claude SDK plan.")
    if plan.get("mode") not in {"review", "automatic"}:
        raise AdapterError("Rename plan has an invalid mode.")
    scope = plan.get("scope", {})
    _scope_directory(scope)
    if scope.get("kind") != "directory" or scope.get("include_worktrees", False):
        raise AdapterError(
            "Claude rename plans must use one exact directory without worktree expansion."
        )
    if not isinstance(scope.get("include_current_session", False), bool):
        raise AdapterError("Rename plan has an invalid current-session policy.")
    excluded_session_ids = scope.get("excluded_session_ids", [])
    if not isinstance(excluded_session_ids, list) or not all(
        isinstance(value, str) for value in excluded_session_ids
    ):
        raise AdapterError("Rename plan has invalid excluded session IDs.")
    type_language = plan.get("type_language")
    if type_language not in {"en", "zh"}:
        raise AdapterError("Rename plan has an invalid TYPE language.")
    title_timezone = plan.get("title_timezone")
    _parse_timezone(title_timezone)
    items = plan.get("items")
    if not isinstance(items, list) or not items:
        raise AdapterError("Rename plan contains no items.")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise AdapterError("Rename plan contains an invalid item.")
        session_id = _validate_uuid(item.get("session_id"))
        if session_id in seen:
            raise AdapterError(f"Duplicate session_id in rename plan: {session_id}")
        if session_id in excluded_session_ids:
            raise AdapterError(
                f"Rename plan contains an excluded session: {session_id}"
            )
        seen.add(session_id)
        created_at = item.get("created_at")
        _validate_title(item.get("after"), created_at, title_timezone, type_language)
        if not isinstance(item.get("before"), str) or item["before"] == item["after"]:
            raise AdapterError(f"Rename plan has an invalid before title: {session_id}")
        if not isinstance(
            item.get("evidence_sha256"), str
        ) or not SHA256_PATTERN.fullmatch(item["evidence_sha256"]):
            raise AdapterError(f"Rename plan lacks topic evidence: {session_id}")
        file_size = item.get("file_size")
        if (
            not isinstance(file_size, int)
            or isinstance(file_size, bool)
            or file_size < 0
        ):
            raise AdapterError(
                f"Rename plan lacks a reliable local file size: {session_id}"
            )
        if file_size > MAX_SAFE_SESSION_BYTES:
            raise AdapterError(
                f"Rename plan contains an oversized session: {session_id}"
            )
        lookup_directory = item.get("lookup_directory")
        cwd = item.get("cwd")
        if scope.get("kind") == "all_projects":
            if not isinstance(cwd, str) or not cwd or lookup_directory != cwd:
                raise AdapterError(
                    f"All-projects plan item lacks an exact directory: {session_id}"
                )
        else:
            expected_lookup = scope.get("directory")
            if lookup_directory != expected_lookup:
                raise AdapterError(
                    f"Rename plan item does not match its directory scope: {session_id}"
                )
    return digest


def _matches_plan_item(info: Any, item: Mapping[str, Any]) -> bool:
    return (
        _attr(info, "session_id") == item.get("session_id")
        and _attr(info, "created_at") == item.get("created_at")
        and _attr(info, "last_modified") == item.get("last_modified")
        and _attr(info, "file_size") == item.get("file_size")
        and _attr(info, "cwd") == item.get("cwd")
        and _current_title(info) == item.get("before")
    )


def _verified_title(
    sdk: Any, scope: Mapping[str, Any], item: Mapping[str, Any]
) -> bool:
    info = _exact_listed_info(sdk, scope, item["session_id"])
    return info is not None and _attr(info, "custom_title") == item["after"]


def apply_plan(
    sdk: Any,
    plan: Mapping[str, Any],
    confirmed_digest: str,
    automatic: bool,
) -> list[dict[str, str]]:
    digest = _validate_plan(plan)
    if confirmed_digest != digest:
        raise AdapterError("Confirmation digest does not match the sealed rename plan.")
    if plan["mode"] == "automatic" and not automatic:
        raise AdapterError(
            "An automatic plan also requires the explicit --automatic apply flag."
        )
    if plan["mode"] == "review" and automatic:
        raise AdapterError("A review plan cannot be applied as an automatic plan.")

    results: list[dict[str, str]] = []
    for item in plan["items"]:
        result = {"before": item["before"], "after": item["after"], "result": ""}
        runtime_current_session = os.environ.get("CLAUDE_CODE_SESSION_ID")
        if runtime_current_session == item["session_id"] and not plan["scope"].get(
            "include_current_session", False
        ):
            result["result"] = "Skipped — current session"
            results.append(result)
            continue
        try:
            info = _exact_listed_info(sdk, plan["scope"], item["session_id"])
            if info is None or not _matches_plan_item(info, item):
                result["result"] = "Skipped — changed since preview"
                results.append(result)
                continue

            messages = list(
                sdk.get_session_messages(
                    item["session_id"],
                    directory=item.get("lookup_directory"),
                    limit=None,
                    offset=0,
                )
            )
            if _message_fingerprint(messages) != item["evidence_sha256"]:
                result["result"] = "Skipped — changed since preview"
                results.append(result)
                continue

            final_preflight = _exact_listed_info(sdk, plan["scope"], item["session_id"])
            if final_preflight is None or not _matches_plan_item(final_preflight, item):
                result["result"] = "Skipped — changed since preview"
                results.append(result)
                continue

            try:
                sdk.rename_session(
                    item["session_id"],
                    item["after"],
                    directory=item.get("lookup_directory"),
                )
            except (
                Exception
            ) as exc:  # The write may have succeeded before a transport error.
                if _verified_title(sdk, plan["scope"], item):
                    result["result"] = "Renamed"
                else:
                    result["result"] = f"Failed — {type(exc).__name__}"
                results.append(result)
                continue

            result["result"] = (
                "Renamed"
                if _verified_title(sdk, plan["scope"], item)
                else "Failed — verification mismatch"
            )
        except Exception as exc:
            result["result"] = f"Failed — {type(exc).__name__}"
            results.append(result)
            continue
        results.append(result)
    return results


def _markdown_cell(value: str) -> str:
    visible = "".join(
        (
            " / "
            if character in {"\r", "\n"}
            else (
                f"U+{ord(character):04X}"
                if unicodedata.category(character) in {"Cc", "Cf"}
                else character
            )
        )
        for character in value
    )
    escaped = html.escape(visible, quote=False)
    markdown_special = frozenset("\\|`*_[]()!")
    return "".join(
        f"\\{character}" if character in markdown_special else character
        for character in escaped
    )


def _markdown_preview(plan: Mapping[str, Any]) -> str:
    lines = ["| Before | After |", "| --- | --- |"]
    lines.extend(
        f"| {_markdown_cell(item['before'])} | {_markdown_cell(item['after'])} |"
        for item in plan["items"]
    )
    lines.extend(("", f"Plan digest: `{plan['plan_digest']}`"))
    return "\n".join(lines)


def _markdown_results(results: list[Mapping[str, str]]) -> str:
    lines = ["| Before | After | Result |", "| --- | --- | --- |"]
    lines.extend(
        f"| {_markdown_cell(item['before'])} | {_markdown_cell(item['after'])} | {_markdown_cell(item['result'])} |"
        for item in results
    )
    return "\n".join(lines)


def _sdk_version() -> str | None:
    try:
        return importlib.metadata.version("claude-agent-sdk")
    except importlib.metadata.PackageNotFoundError:
        return None


def _version_tuple(value: str) -> tuple[int, int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _version_supported(value: str | None) -> bool:
    if value is None:
        return False
    installed = _version_tuple(value)
    minimum = _version_tuple(MINIMUM_SDK_VERSION)
    maximum = _version_tuple(MAXIMUM_SDK_VERSION_EXCLUSIVE)
    return (
        installed is not None
        and minimum is not None
        and maximum is not None
        and minimum <= installed < maximum
    )


def _load_sdk() -> Any:
    try:
        import claude_agent_sdk as sdk
    except ImportError as exc:
        raise AdapterError(
            "Claude Agent SDK is not installed. Install requirements-claude.txt in a virtual environment."
        ) from exc
    missing = [
        name
        for name in (
            "list_sessions",
            "get_session_messages",
            "get_session_info",
            "rename_session",
        )
        if not callable(getattr(sdk, name, None))
    ]
    if missing:
        raise AdapterError(
            "Claude Agent SDK lacks required session APIs: " + ", ".join(missing)
        )
    version = _sdk_version()
    if not _version_supported(version):
        raise AdapterError(
            f"Unsupported Claude Agent SDK version {version!r}; install >= {MINIMUM_SDK_VERSION} "
            f"and < {MAXIMUM_SDK_VERSION_EXCLUSIVE}."
        )
    return sdk


def _add_scope_arguments(parser: argparse.ArgumentParser) -> None:
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--directory", help="Exact Claude Code project directory")
    scope.add_argument(
        "--all-projects",
        action="store_true",
        help="Discover SDK-visible sessions across projects (read-only scope)",
    )
    parser.add_argument(
        "--include-worktrees",
        dest="include_worktrees",
        action="store_true",
        help="Include sibling Git worktrees for read-only discovery; mutation plans reject this scope",
    )
    parser.add_argument(
        "--exclude-session",
        action="append",
        default=[],
        help="Exclude a stable session ID (repeatable)",
    )
    parser.add_argument(
        "--include-current-session",
        action="store_true",
        help="Include CLAUDE_CODE_SESSION_ID only when the user explicitly requested it",
    )
    parser.set_defaults(include_worktrees=False)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safe Claude Code history bridge for Agent Title Renamer Skill"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Check the optional Claude SDK dependency")

    inventory_parser = subparsers.add_parser(
        "inventory", help="List SDK-visible session metadata without mutation"
    )
    _add_scope_arguments(inventory_parser)

    inspect_parser = subparsers.add_parser(
        "inspect", help="Read sampled human text and hash all evidence"
    )
    inspect_scope = inspect_parser.add_mutually_exclusive_group(required=True)
    inspect_scope.add_argument("--directory")
    inspect_scope.add_argument("--all-projects", action="store_true")
    inspect_parser.add_argument("--session", required=True)
    inspect_parser.add_argument("--max-messages", type=int, default=20)
    inspect_parser.add_argument("--max-chars", type=int, default=8000)

    preview_parser = subparsers.add_parser(
        "preview", help="Seal proposals into a zero-write rename plan"
    )
    _add_scope_arguments(preview_parser)
    preview_parser.add_argument("--timezone", required=True, dest="title_timezone")
    preview_parser.add_argument("--type-language", required=True, choices=("en", "zh"))
    preview_parser.add_argument(
        "--mode", choices=("review", "automatic"), default="review"
    )
    preview_parser.add_argument("--proposals", required=True, type=Path)
    preview_parser.add_argument("--plan", required=True, type=Path)
    preview_parser.add_argument(
        "--format", choices=("markdown", "json"), default="markdown"
    )

    apply_parser = subparsers.add_parser(
        "apply", help="Revalidate and apply one sealed plan"
    )
    apply_parser.add_argument("--plan", required=True, type=Path)
    apply_parser.add_argument("--confirm", required=True, dest="confirmed_digest")
    apply_parser.add_argument("--automatic", action="store_true")
    apply_parser.add_argument(
        "--format", choices=("markdown", "json"), default="markdown"
    )
    return parser


def main(argv: Sequence[str] | None = None, sdk: Any | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            active_sdk = sdk or _load_sdk()
            required = all(
                callable(getattr(active_sdk, name, None))
                for name in (
                    "list_sessions",
                    "get_session_messages",
                    "get_session_info",
                    "rename_session",
                )
            )
            sdk_version = _sdk_version()
            version_supported = _version_supported(sdk_version)
            print(
                json.dumps(
                    {
                        "ok": required and version_supported,
                        "adapter_version": ADAPTER_VERSION,
                        "sdk_version": sdk_version,
                        "minimum_tested_sdk": MINIMUM_SDK_VERSION,
                        "maximum_tested_sdk_exclusive": MAXIMUM_SDK_VERSION_EXCLUSIVE,
                        "version_supported": version_supported,
                        "required_session_apis": required,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if required and version_supported else 2

        active_sdk = sdk or _load_sdk()
        if args.command == "inventory":
            scope = _scope_from_args(args)
            payload = inventory(active_sdk, scope)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        if args.command == "inspect":
            if args.max_messages <= 0 or args.max_chars <= 0:
                raise AdapterError("--max-messages and --max-chars must be positive.")
            session_id = _validate_uuid(args.session)
            inspect_scope = (
                {"kind": "all_projects", "include_worktrees": True}
                if args.all_projects
                else {
                    "kind": "directory",
                    "directory": _canonical_directory(args.directory),
                    "include_worktrees": True,
                }
            )
            directory = _resolve_inspection_directory(
                active_sdk, session_id, inspect_scope
            )
            payload = inspect_session(
                active_sdk,
                session_id,
                directory,
                args.max_messages,
                args.max_chars,
            )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        if args.command == "preview":
            scope = _scope_from_args(args)
            proposals = _load_proposals(args.proposals)
            plan = build_plan(
                active_sdk,
                scope,
                proposals,
                args.title_timezone,
                args.type_language,
                args.mode,
            )
            _write_private_json(args.plan, plan)
            if args.format == "json":
                print(
                    json.dumps(
                        {"plan": str(args.plan), **plan}, ensure_ascii=False, indent=2
                    )
                )
            else:
                print(_markdown_preview(plan))
            return 0

        if args.command == "apply":
            plan = _load_plan(args.plan)
            results = apply_plan(
                active_sdk, plan, args.confirmed_digest, args.automatic
            )
            if args.format == "json":
                print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
            else:
                print(_markdown_results(results))
            return 0 if all(item["result"] == "Renamed" for item in results) else 1
    except (AdapterError, OSError, ValueError) as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2
    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
