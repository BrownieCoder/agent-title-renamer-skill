from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import stat
import tempfile
import unittest
from unittest import mock
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = (
    REPO_ROOT / "skills" / "agent-title-renamer" / "scripts" / "claude_adapter.py"
)
SPEC = importlib.util.spec_from_file_location("claude_adapter", ADAPTER_PATH)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


SESSION_ID = "550e8400-e29b-41d4-a716-446655440000"
SECOND_SESSION_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
CREATED_AT = int(datetime(2026, 9, 2, 16, 30, tzinfo=timezone.utc).timestamp() * 1000)
LAST_MODIFIED = int(datetime(2026, 12, 25, tzinfo=timezone.utc).timestamp() * 1000)


@dataclass
class FakeInfo:
    session_id: str
    summary: str
    last_modified: int
    file_size: int | None = 4096
    custom_title: str | None = None
    first_prompt: str | None = None
    git_branch: str | None = None
    cwd: str | None = None
    tag: str | None = None
    created_at: int | None = None


@dataclass
class FakeMessage:
    type: str
    uuid: str
    session_id: str
    message: object
    parent_tool_use_id: str | None = None
    parent_agent_id: str | None = None


class FakeSDK:
    def __init__(self, directory: str = "/project") -> None:
        self.info = FakeInfo(
            session_id=SESSION_ID,
            summary="Improve batch text display",
            last_modified=LAST_MODIFIED,
            first_prompt="Improve the batch text display.",
            cwd=directory,
            created_at=CREATED_AT,
        )
        self.messages = [
            FakeMessage(
                type="user",
                uuid="message-1",
                session_id=SESSION_ID,
                message={"role": "user", "content": "Improve the batch text display."},
            ),
            FakeMessage(
                type="assistant",
                uuid="message-2",
                session_id=SESSION_ID,
                message={
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Updated wrapping and truncation."},
                        {"type": "tool_use", "input": {"private": "not emitted"}},
                    ],
                },
            ),
        ]
        self.rename_calls: list[tuple[str, str, str | None]] = []
        self.fail_after_write = False

    def list_sessions(
        self,
        directory=None,
        limit=None,
        offset=0,
        include_worktrees=True,
    ):
        if directory is not None and directory != self.info.cwd:
            return []
        return [self.info]

    def get_session_info(self, session_id, directory=None):
        if session_id != self.info.session_id:
            return None
        if directory is not None and directory != self.info.cwd:
            return None
        return self.info

    def get_session_messages(self, session_id, directory=None, limit=None, offset=0):
        if session_id != self.info.session_id:
            return []
        return list(self.messages)

    def rename_session(self, session_id, title, directory=None):
        self.rename_calls.append((session_id, title, directory))
        self.info = replace(
            self.info,
            summary=title,
            custom_title=title,
            last_modified=self.info.last_modified + 1,
        )
        if self.fail_after_write:
            raise TimeoutError("simulated timeout after append")


class MultiSessionSDK(FakeSDK):
    def __init__(self) -> None:
        super().__init__()
        self.second_info = replace(
            self.info,
            session_id=SECOND_SESSION_ID,
            summary="Fix login redirect",
            first_prompt="Fix the timeout login redirect.",
        )
        self.second_messages = [
            FakeMessage(
                type="user",
                uuid="second-message-1",
                session_id=SECOND_SESSION_ID,
                message={"role": "user", "content": "Fix the timeout login redirect."},
            )
        ]
        self.fail_second_reads = False

    def list_sessions(
        self, directory=None, limit=None, offset=0, include_worktrees=True
    ):
        return [self.info, self.second_info]

    def get_session_info(self, session_id, directory=None):
        if session_id == SECOND_SESSION_ID:
            if self.fail_second_reads:
                raise OSError("simulated read failure")
            return self.second_info
        return super().get_session_info(session_id, directory)

    def get_session_messages(self, session_id, directory=None, limit=None, offset=0):
        if session_id == SECOND_SESSION_ID:
            if self.fail_second_reads:
                raise OSError("simulated read failure")
            return list(self.second_messages)
        return super().get_session_messages(session_id, directory, limit, offset)

    def rename_session(self, session_id, title, directory=None):
        if session_id == SECOND_SESSION_ID:
            self.rename_calls.append((session_id, title, directory))
            self.second_info = replace(
                self.second_info,
                summary=title,
                custom_title=title,
                last_modified=self.second_info.last_modified + 1,
            )
            return
        super().rename_session(session_id, title, directory)


def scope(directory: str = "/project") -> dict[str, object]:
    return {"kind": "directory", "directory": directory, "include_worktrees": False}


def bound_proposal(
    info: FakeInfo, messages: list[FakeMessage], after: str
) -> dict[str, object]:
    return {
        "session_id": info.session_id,
        "before": info.custom_title or info.summary,
        "created_at": info.created_at,
        "last_modified": info.last_modified,
        "file_size": info.file_size,
        "cwd": info.cwd,
        "evidence_sha256": adapter._message_fingerprint(messages),
        "after": after,
    }


def proposal(
    after: str = "0903｜OPT｜Batch text display", sdk: FakeSDK | None = None
) -> list[dict[str, object]]:
    source = sdk or FakeSDK()
    return [bound_proposal(source.info, source.messages, after)]


def sealed_plan(sdk: FakeSDK, mode: str = "review") -> dict[str, object]:
    return adapter.build_plan(
        sdk,
        scope(sdk.info.cwd or "/project"),
        proposal(sdk=sdk),
        "Asia/Shanghai",
        "en",
        mode,
    )


class ClaudeAdapterTests(unittest.TestCase):
    def test_supported_sdk_version_range_fails_closed(self):
        self.assertFalse(adapter._version_supported(None))
        self.assertFalse(adapter._version_supported("0.1.73"))
        self.assertTrue(adapter._version_supported("0.1.74"))
        self.assertTrue(adapter._version_supported("0.2.152"))
        self.assertFalse(adapter._version_supported("0.3.0"))

    def test_inventory_omits_unneeded_prompt_branch_tag_and_duplicate_titles(self):
        sdk = FakeSDK()
        payload = adapter.inventory(sdk, scope())
        session = payload["sessions"][0]
        self.assertEqual(
            set(session),
            {
                "session_id",
                "current_title",
                "created_at",
                "last_modified",
                "file_size",
                "cwd",
            },
        )

    def test_preview_plan_uses_created_at_and_makes_zero_writes(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)

        self.assertEqual(plan["items"][0]["after"], "0903｜OPT｜Batch text display")
        self.assertEqual(plan["items"][0]["created_at"], CREATED_AT)
        self.assertEqual(sdk.rename_calls, [])
        self.assertTrue(plan["plan_digest"].startswith("sha256:"))

    def test_updated_time_cannot_supply_the_title_date(self):
        sdk = FakeSDK()
        with self.assertRaisesRegex(adapter.AdapterError, "does not match created_at"):
            adapter.build_plan(
                sdk,
                scope(),
                proposal("1225｜OPT｜Batch text display", sdk=sdk),
                "Asia/Shanghai",
                "en",
                "review",
            )
        self.assertEqual(sdk.rename_calls, [])

    def test_type_language_cannot_mix(self):
        sdk = FakeSDK()
        with self.assertRaisesRegex(
            adapter.AdapterError, "does not match the plan language"
        ):
            adapter.build_plan(
                sdk,
                scope(),
                proposal("0903｜优化｜批次文字显示", sdk=sdk),
                "Asia/Shanghai",
                "en",
                "review",
            )

    def test_missing_created_at_cannot_be_proposed(self):
        sdk = FakeSDK()
        sdk.info = replace(sdk.info, created_at=None)
        with self.assertRaisesRegex(adapter.AdapterError, "no valid creation time"):
            sealed_plan(sdk)
        self.assertEqual(sdk.rename_calls, [])

    def test_apply_revalidates_renames_once_and_verifies(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)

        results = adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=False)

        self.assertEqual(results[0]["result"], "Renamed")
        self.assertEqual(len(sdk.rename_calls), 1)
        self.assertEqual(sdk.info.custom_title, "0903｜OPT｜Batch text display")

    def test_wrong_digest_fails_before_any_write(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)
        with self.assertRaisesRegex(adapter.AdapterError, "Confirmation digest"):
            adapter.apply_plan(sdk, plan, "sha256:not-the-plan", automatic=False)
        self.assertEqual(sdk.rename_calls, [])

    def test_tampered_plan_fails_before_any_write(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)
        plan["items"][0]["after"] = "0903｜FIX｜Something else"
        with self.assertRaisesRegex(adapter.AdapterError, "digest does not match"):
            adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=False)
        self.assertEqual(sdk.rename_calls, [])

    def test_forged_cross_project_plan_is_rejected_even_with_new_digest(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)
        plan["scope"] = {"kind": "all_projects", "include_worktrees": False}
        unsigned = dict(plan)
        unsigned.pop("plan_digest")
        plan["plan_digest"] = adapter._sha256(unsigned)
        with self.assertRaisesRegex(adapter.AdapterError, "one exact directory"):
            adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=False)
        self.assertEqual(sdk.rename_calls, [])

    def test_title_drift_is_skipped(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)
        sdk.info = replace(sdk.info, summary="User changed this title")

        results = adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=False)

        self.assertEqual(results[0]["result"], "Skipped — changed since preview")
        self.assertEqual(sdk.rename_calls, [])

    def test_message_drift_is_skipped(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)
        sdk.messages.append(
            FakeMessage(
                type="user",
                uuid="message-3",
                session_id=SESSION_ID,
                message={"role": "user", "content": "New direction."},
            )
        )

        results = adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=False)

        self.assertEqual(results[0]["result"], "Skipped — changed since preview")
        self.assertEqual(sdk.rename_calls, [])

    def test_message_change_between_inspect_and_preview_rejects_stale_proposal(self):
        sdk = FakeSDK()
        stale_proposal = proposal(sdk=sdk)
        sdk.messages.append(
            FakeMessage(
                type="user",
                uuid="message-after-inspect",
                session_id=SESSION_ID,
                message={
                    "role": "user",
                    "content": "The topic changed after inspection.",
                },
            )
        )
        with self.assertRaisesRegex(adapter.AdapterError, "changed after inspection"):
            adapter.build_plan(
                sdk,
                scope(),
                stale_proposal,
                "Asia/Shanghai",
                "en",
                "review",
            )
        self.assertEqual(sdk.rename_calls, [])

    def test_oversized_session_fails_closed_before_preview(self):
        sdk = FakeSDK()
        sdk.info = replace(sdk.info, file_size=adapter.MAX_SAFE_SESSION_BYTES + 1)
        with self.assertRaisesRegex(adapter.AdapterError, "safe metadata window"):
            adapter.build_plan(
                sdk,
                scope(),
                proposal(sdk=sdk),
                "Asia/Shanghai",
                "en",
                "review",
            )
        self.assertEqual(sdk.rename_calls, [])

    def test_automatic_mode_requires_plan_and_apply_authorization(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk, mode="automatic")
        with self.assertRaisesRegex(adapter.AdapterError, "explicit --automatic"):
            adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=False)
        self.assertEqual(sdk.rename_calls, [])

        results = adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=True)
        self.assertEqual(results[0]["result"], "Renamed")

    def test_review_plan_rejects_automatic_flag(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)
        with self.assertRaisesRegex(
            adapter.AdapterError, "cannot be applied as an automatic"
        ):
            adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=True)
        self.assertEqual(sdk.rename_calls, [])

    def test_timeout_after_write_is_verified_without_retry(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)
        sdk.fail_after_write = True

        results = adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=False)

        self.assertEqual(results[0]["result"], "Renamed")
        self.assertEqual(len(sdk.rename_calls), 1)

    def test_summary_change_without_custom_title_is_not_verified(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)

        def summary_only_rename(session_id, title, directory=None):
            sdk.rename_calls.append((session_id, title, directory))
            sdk.info = replace(sdk.info, summary=title, custom_title=None)

        sdk.rename_session = summary_only_rename
        results = adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=False)
        self.assertEqual(results[0]["result"], "Failed — verification mismatch")
        self.assertEqual(len(sdk.rename_calls), 1)

    def test_inspection_emits_text_but_not_tool_inputs(self):
        sdk = FakeSDK()
        sdk.messages[1].message["content"].extend(
            [
                {"type": "tool_result", "content": "SECRET_TOOL_RESULT"},
                {"type": "thinking", "text": "SECRET_THINKING"},
            ]
        )
        payload = adapter.inspect_session(sdk, SESSION_ID, "/project", 20, 8000)
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertIn("Updated wrapping and truncation", rendered)
        self.assertNotIn("not emitted", rendered)
        self.assertNotIn("SECRET_TOOL_RESULT", rendered)
        self.assertNotIn("SECRET_THINKING", rendered)
        self.assertTrue(payload["sdk_visible_evidence_complete"])
        self.assertEqual(
            payload["proposal_base"]["before"], "Improve batch text display"
        )

    def test_inspection_rejects_unknown_or_out_of_scope_session(self):
        sdk = FakeSDK()
        with self.assertRaisesRegex(
            adapter.AdapterError, "not found in the requested scope"
        ):
            adapter.inspect_session(sdk, SECOND_SESSION_ID, "/project", 20, 8000)

    def test_duplicate_uuid_across_projects_fails_closed(self):
        sdk = FakeSDK()
        duplicate = replace(sdk.info, cwd="/copied-project")
        sdk.list_sessions = lambda **kwargs: [sdk.info, duplicate]
        with self.assertRaisesRegex(
            adapter.AdapterError, "ambiguous across the requested scope"
        ):
            adapter.build_plan(
                sdk,
                scope(),
                proposal(sdk=sdk),
                "Asia/Shanghai",
                "en",
                "review",
            )
        self.assertEqual(sdk.rename_calls, [])

    def test_all_projects_requires_a_stable_session_directory(self):
        sdk = FakeSDK()
        sdk.info = replace(sdk.info, cwd=None)
        with self.assertRaisesRegex(
            adapter.AdapterError, "no stable project directory"
        ):
            adapter._lookup_directory(
                sdk.info,
                {"kind": "all_projects", "include_worktrees": False},
            )

    def test_exact_scope_uses_requested_directory_not_stale_session_cwd(self):
        sdk = FakeSDK()
        sdk.info = replace(sdk.info, cwd="/original-project")
        sdk.list_sessions = lambda **kwargs: [sdk.info]
        sdk.get_session_info = lambda session_id, directory=None: sdk.info
        plan = adapter.build_plan(
            sdk,
            scope("/copied-project"),
            proposal(sdk=sdk),
            "Asia/Shanghai",
            "en",
            "review",
        )
        self.assertEqual(plan["items"][0]["lookup_directory"], "/copied-project")
        self.assertEqual(plan["items"][0]["cwd"], "/original-project")

    def test_cross_project_inventory_is_discovery_only(self):
        sdk = FakeSDK()
        payload = adapter.inventory(
            sdk,
            {"kind": "all_projects", "include_worktrees": False},
        )
        self.assertFalse(payload["physical_inventory_complete"])
        self.assertFalse(payload["selected_id_mutation_safe"])
        with self.assertRaisesRegex(
            adapter.AdapterError, "require one exact directory"
        ):
            adapter.build_plan(
                sdk,
                {"kind": "all_projects", "include_worktrees": False},
                proposal(sdk=sdk),
                "Asia/Shanghai",
                "en",
                "review",
            )

    def test_all_projects_inspection_rejects_ambiguous_uuid(self):
        sdk = FakeSDK()
        duplicate = replace(sdk.info, cwd="/copied-project")
        sdk.list_sessions = lambda **kwargs: [sdk.info, duplicate]
        with self.assertRaisesRegex(adapter.AdapterError, "UUID is ambiguous"):
            adapter._resolve_inspection_directory(
                sdk,
                SESSION_ID,
                {"kind": "all_projects", "include_worktrees": True},
            )

    def test_item_read_failure_does_not_hide_prior_results(self):
        sdk = MultiSessionSDK()
        plan = adapter.build_plan(
            sdk,
            scope(),
            [
                *proposal(sdk=sdk),
                bound_proposal(
                    sdk.second_info,
                    sdk.second_messages,
                    "0903｜FIX｜Login redirect",
                ),
            ],
            "Asia/Shanghai",
            "en",
            "review",
        )
        sdk.fail_second_reads = True

        results = adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=False)

        by_title = {item["after"]: item["result"] for item in results}
        self.assertEqual(by_title["0903｜OPT｜Batch text display"], "Renamed")
        self.assertEqual(by_title["0903｜FIX｜Login redirect"], "Failed — OSError")
        self.assertEqual(len(sdk.rename_calls), 1)

    def test_exact_session_disappearance_cannot_fall_back_to_worktree(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)
        sdk.list_sessions = lambda **kwargs: []

        results = adapter.apply_plan(sdk, plan, plan["plan_digest"], automatic=False)

        self.assertEqual(results[0]["result"], "Skipped — changed since preview")
        self.assertEqual(sdk.rename_calls, [])

    def test_plan_file_is_private_and_never_overwritten(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            adapter._write_private_json(path, plan)
            permissions = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(permissions, stat.S_IRUSR | stat.S_IWUSR)
            with self.assertRaisesRegex(adapter.AdapterError, "Refusing to overwrite"):
                adapter._write_private_json(path, plan)

    def test_cli_preview_prints_exact_two_column_table(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = FakeSDK(str(Path(directory).resolve()))
            proposals_path = Path(directory) / "proposals.json"
            plan_path = Path(directory) / "plan.json"
            proposals_path.write_text(
                json.dumps({"items": proposal(sdk=sdk)}),
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = adapter.main(
                    [
                        "preview",
                        "--directory",
                        directory,
                        "--timezone",
                        "Asia/Shanghai",
                        "--type-language",
                        "en",
                        "--proposals",
                        str(proposals_path),
                        "--plan",
                        str(plan_path),
                    ],
                    sdk=sdk,
                )
            self.assertEqual(exit_code, 0)
            self.assertTrue(output.getvalue().startswith("| Before | After |\n"))
            self.assertNotIn("| Result |", output.getvalue())
            self.assertEqual(sdk.rename_calls, [])

    def test_current_claude_session_is_excluded_by_default(self):
        sdk = FakeSDK()
        namespace = adapter._build_parser().parse_args(["inventory", "--all-projects"])
        with mock.patch.dict("os.environ", {"CLAUDE_CODE_SESSION_ID": SESSION_ID}):
            selected_scope = adapter._scope_from_args(namespace)
        payload = adapter.inventory(sdk, selected_scope)
        self.assertEqual(payload["sessions"], [])

    def test_explicit_current_session_inclusion_is_respected(self):
        namespace = adapter._build_parser().parse_args(
            ["inventory", "--all-projects", "--include-current-session"]
        )
        with mock.patch.dict("os.environ", {"CLAUDE_CODE_SESSION_ID": SESSION_ID}):
            selected_scope = adapter._scope_from_args(namespace)
        self.assertEqual(selected_scope["excluded_session_ids"], [])
        self.assertTrue(selected_scope["include_current_session"])

    def test_apply_skips_runtime_current_session_unless_explicitly_included(self):
        sdk = FakeSDK()
        plan = sealed_plan(sdk)
        with mock.patch.dict("os.environ", {"CLAUDE_CODE_SESSION_ID": SESSION_ID}):
            results = adapter.apply_plan(
                sdk, plan, plan["plan_digest"], automatic=False
            )
        self.assertEqual(results[0]["result"], "Skipped — current session")
        self.assertEqual(sdk.rename_calls, [])

    def test_markdown_escapes_untrusted_title_content(self):
        plan = {
            "items": [{"before": "<b>bad</b> | row\nnext", "after": "0903｜OPT｜Safe"}],
            "plan_digest": "sha256:test",
        }
        rendered = adapter._markdown_preview(plan)
        self.assertIn("&lt;b&gt;bad&lt;/b&gt; \\| row / next", rendered)
        self.assertNotIn("<b>bad</b>", rendered)

    def test_markdown_neutralizes_remote_images_and_terminal_controls(self):
        rendered = adapter._markdown_cell("![x](https://tracker.example/pixel)\x1b")
        self.assertIn(r"\!\[x\]\(https://tracker.example/pixel\)", rendered)
        self.assertIn("U+001B", rendered)

    def test_message_sample_respects_global_character_budget(self):
        sdk = FakeSDK()
        sdk.messages = [
            FakeMessage(
                type="user",
                uuid=f"message-{index}",
                session_id=SESSION_ID,
                message={"role": "user", "content": "abcdef"},
            )
            for index in range(10)
        ]
        sampled = adapter._sample_messages(sdk.messages, max_messages=10, max_chars=3)
        self.assertLessEqual(sum(len(item["text"]) for item in sampled), 3)

    def test_title_rejects_invisible_direction_override(self):
        with self.assertRaisesRegex(adapter.AdapterError, "control or invisible"):
            adapter._validate_title(
                "0903｜OPT｜Safe\u202Etxt",
                CREATED_AT,
                "Asia/Shanghai",
                "en",
            )


if __name__ == "__main__":
    unittest.main()
