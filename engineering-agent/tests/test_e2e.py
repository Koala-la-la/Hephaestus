"""端到端集成测试——五层协作验证。

验证五层架构从 Prompt 组装到 confirm token 的完整流程：
Prompt → Harness → Context → Loop → Graph → Confirm

这是"局部都清楚、拼起来可能打架"的防线——
五层各自独立测试通过，但五层之间的咬合需要端到端验证。
"""

import subprocess

import pytest

from engineering_agent.context.feedback import FeedbackKeeper
from engineering_agent.context.matrix import ContextMatrix
from engineering_agent.graph.finding_router import FindingRouter
from engineering_agent.harness import Harness
from engineering_agent.loop.gate_checker import CODING_EXIT_GATES, GateChecker
from engineering_agent.loop.state_tracker import LoopStateTracker
from engineering_agent.manifest.models import (
    FindingSeverity,
    FindingSource,
    LoopType,
    ReviewFinding,
    SDLCPhase,
)
from engineering_agent.prompt.builder import PromptBuilder
from engineering_agent.prompt.confirm import (
    ConfirmManager,
    ConfirmRequest,
    ConfirmType,
)
from engineering_agent.prompt.protocol import L3Protocol, TaskComplete


@pytest.fixture
def git_repo(tmp_path):
    """临时 git 仓库，含已 commit 的 spec.md。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=repo, capture_output=True)
    spec = repo / "spec.md"
    spec.write_text("# Spec\n\n## 1. 背景\n\n实现登录接口", encoding="utf-8")
    subprocess.run(["git", "add", "spec.md"], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init spec"], cwd=repo, capture_output=True)
    return repo


def test_e2e_prompt_to_harness(git_repo, tmp_path):
    """端到端 1: Prompt 组装 + Harness spec 锁定 + 权限检查。

    验证：PromptBuilder L2 从 manifest 读 spec_sha/task →
    Harness freeze → check_tool_permission 放行 edit_file / 拒绝 kubectl。
    """
    manifest_dir = tmp_path / "manifest"
    harness = Harness(manifest_dir=manifest_dir, repo_root=git_repo)

    harness.manifest_store.write("phase2", {"tasks": [
        {"id": "T-1", "status": "pending", "spec_refs": ["4.2"]},
    ]})

    # 冻结 spec + 更新 manifest
    sha = harness.freeze_spec(git_repo / "spec.md")
    harness.manifest_store.update_field("common", "spec_sha", sha)
    harness.manifest_store.update_field("common", "spec_version", "v1")
    assert harness.spec_frozen

    # Prompt 组装
    prompt = PromptBuilder().build_prompt("coding", harness.manifest_store)
    assert "执行者" in prompt.l1_identity
    assert "T-1" in prompt.l2_task_spec
    assert "4.2" in prompt.l2_task_spec
    assert sha in prompt.l2_task_spec
    assert "tool_call" in prompt.l3_protocol

    # 权限检查——spec 已冻结，edit_file 放行
    assert harness.check_tool_permission(SDLCPhase.CODING, "edit_file").allowed is True
    # read_file 放行（L0）
    assert harness.check_tool_permission(SDLCPhase.CODING, "read_file").allowed is True
    # kubectl 拒绝（L2）
    assert harness.check_tool_permission(SDLCPhase.RELEASE, "kubectl_apply").allowed is False


def test_e2e_harness_to_loop(git_repo, tmp_path):
    """端到端 2: Harness manifest + Loop GateChecker + LoopStateTracker。

    验证：manifest 写 phase3 → GateChecker 校验 FAIL → 修正 → PASS →
    LoopStateTracker 更新 + clear_pending_findings。
    """
    manifest_dir = tmp_path / "manifest"
    harness = Harness(manifest_dir=manifest_dir, repo_root=git_repo)
    harness.freeze_spec(git_repo / "spec.md")

    # 写 manifest phase3（有 FAIL）
    harness.manifest_store.write("phase3", {
        "task_status_all_done": False,
        "lint_baseline_delta": 0,
        "compile_passed": False,
        "test_regression_passed": True,
        "new_test_passed": True,
        "review_passed": True,
        "all_traces_exist": True,
    })

    # GateChecker → 有 FAIL
    checker = GateChecker()
    assert checker.check_all(CODING_EXIT_GATES, harness.manifest_store).all_pass is False

    # 修正
    harness.manifest_store.update_field("phase3", "task_status_all_done", True)
    harness.manifest_store.update_field("phase3", "compile_passed", True)

    # 重新校验 → PASS
    assert checker.check_all(CODING_EXIT_GATES, harness.manifest_store).all_pass is True

    # LoopStateTracker
    tracker = LoopStateTracker(harness.manifest_store)
    tracker.init_state(SDLCPhase.CODING, "T-1")
    tracker.update_location(loop_type=LoopType.A)
    tracker.update_snapshot(review_round=1, pending_findings=["F-1"])
    assert tracker.get_state().location.current_task_id == "T-1"

    tracker.clear_pending_findings()
    assert tracker.get_state().snapshot.pending_findings == []


def test_e2e_loop_to_graph(git_repo, tmp_path):
    """端到端 3: Loop review findings + Graph FindingRouter 路由。

    验证：finding 写 manifest → FindingRouter 三级分级路由。
    """
    manifest_dir = tmp_path / "manifest"
    harness = Harness(manifest_dir=manifest_dir, repo_root=git_repo)
    harness.freeze_spec(git_repo / "spec.md")

    # 创建 findings 并写 manifest
    machine_p0 = ReviewFinding(
        severity=FindingSeverity.P0, source=FindingSource.MACHINE,
        file="auth/login.go", line=42,
    )
    agent_p0 = ReviewFinding(
        severity=FindingSeverity.P0, source=FindingSource.AGENT,
        file="auth/session.go",
    )
    p1 = ReviewFinding(
        severity=FindingSeverity.P1, source=FindingSource.AGENT,
        file="auth/utils.go",
    )
    harness.manifest_store.update_field(
        "phase3", "review_findings",
        [f.model_dump(mode="json") for f in [machine_p0, agent_p0, p1]],
    )

    # FindingRouter 三级分级
    router = FindingRouter()
    assert router.route(machine_p0).action == "block"
    assert router.route(machine_p0).overridable is False
    assert router.route(agent_p0).action == "block_overridable"
    assert router.route(agent_p0).overridable is True
    assert router.route(p1).action == "record"

    # 批量
    batch = router.route_batch([machine_p0, agent_p0, p1])
    assert batch.has_block is True
    assert len(batch.blocks) == 2


def test_e2e_full_pipeline(git_repo, tmp_path):
    """端到端 4: 完整流水线——Prompt → Harness → Context → Loop → Graph → Confirm。"""
    manifest_dir = tmp_path / "manifest"
    harness = Harness(manifest_dir=manifest_dir, repo_root=git_repo)

    # === 1. Prompt 层 ===
    harness.manifest_store.write("phase2", {"tasks": [
        {"id": "T-1", "status": "pending", "spec_refs": ["4.2", "5.1"]},
    ]})
    sha = harness.freeze_spec(git_repo / "spec.md")
    harness.manifest_store.update_field("common", "spec_sha", sha)

    prompt = PromptBuilder().build_prompt("coding", harness.manifest_store)
    assert "执行者" in prompt.l1_identity
    assert "T-1" in prompt.l2_task_spec
    assert sha in prompt.l2_task_spec

    # === 2. Harness 层 ===
    assert harness.check_tool_permission(SDLCPhase.CODING, "edit_file").allowed is True
    assert harness.check_tool_permission(SDLCPhase.RELEASE, "kubectl_apply").allowed is False

    # === 3. Context 层 ===
    matrix = ContextMatrix()
    assert "task_spec" in matrix.get_push_types("coding")
    assert "code" not in matrix.get_push_types("coding")

    feedback = FeedbackKeeper()
    feedback.set("lint", "5 warnings")
    feedback.set("lint", "0 warnings")
    assert feedback.get("lint") == "0 warnings"

    # === 4. Loop 层 ===
    harness.manifest_store.write("phase3", {
        "task_status_all_done": True, "lint_baseline_delta": 0,
        "compile_passed": True, "test_regression_passed": True,
        "new_test_passed": True, "review_passed": True,
        "all_traces_exist": True,
    })
    assert GateChecker().check_all(CODING_EXIT_GATES, harness.manifest_store).all_pass is True

    tracker = LoopStateTracker(harness.manifest_store)
    tracker.init_state(SDLCPhase.CODING, "T-1")
    tracker.update_location(loop_type=LoopType.A)
    tracker.update_snapshot(review_round=1, pending_findings=["F-1"])
    tracker.clear_pending_findings()
    assert tracker.get_state().snapshot.pending_findings == []

    # === 5. Graph 层 ===
    router = FindingRouter()
    machine_p0 = ReviewFinding(
        severity=FindingSeverity.P0, source=FindingSource.MACHINE, file="a.go"
    )
    assert router.route(machine_p0).action == "block"

    # === 6. Confirm 层 ===
    output = L3Protocol.parse_output(
        '{"type":"task_complete","id":"T-1","evidence":{"compile_passed":true}}'
    )
    assert isinstance(output, TaskComplete)
    assert output.evidence["compile_passed"] is True

    mgr = ConfirmManager()
    mgr.request(ConfirmRequest("p1", ConfirmType.PHASE_EXIT, "coding", "T-1 完成"))
    mgr.request(ConfirmRequest("o1", ConfirmType.OVERRIDE, "coding", "覆盖 P0"))
    assert mgr.get_pending().request_id == "o1"
    mgr.resolve("o1", True)
    assert mgr.get_pending().request_id == "p1"
    assert mgr.resolve("p1", True).approved is True


def test_e2e_spec_not_frozen_blocks_edit(tmp_path, git_repo):
    """端到端：spec 未冻结 → edit_file 被拒（spec-first 检查）。"""
    harness = Harness(manifest_dir=tmp_path / "manifest", repo_root=git_repo)
    assert not harness.spec_frozen
    result = harness.check_tool_permission(SDLCPhase.CODING, "edit_file")
    assert result.allowed is False
    assert "未冻结" in result.reason
