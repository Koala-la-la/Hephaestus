"""集成验证测试。

验收标准（spec.md Task 7 + §4.5 + §5 Goal State）：
1. 无 spec 拦截 Edit
2. 有 spec 放行 Edit
3. manifest 写 needs_revalidation
"""

import subprocess

import pytest

from engineering_agent.harness import Harness
from engineering_agent.manifest.models import SDLCPhase
from engineering_agent.permissions.levels import DangerLevel


@pytest.fixture
def git_repo(tmp_path):
    """临时 git 仓库，含已 commit 的 spec.md（v1）。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=repo, capture_output=True)
    spec = repo / "spec.md"
    spec.write_text("# Spec\n\nv1 content", encoding="utf-8")
    subprocess.run(["git", "add", "spec.md"], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=repo, capture_output=True
    )
    return repo


def test_case1_spec_not_frozen_blocks_edit(tmp_path, git_repo):
    """case 1: spec 未冻结 → edit_file 被拒（无 spec 不许改代码）。"""
    harness = Harness(
        manifest_dir=tmp_path / "manifest",
        repo_root=git_repo,
    )
    assert not harness.spec_frozen

    result = harness.check_tool_permission(SDLCPhase.CODING, "edit_file")
    assert result.allowed is False
    assert "未冻结" in result.reason


def test_case2_spec_uncommitted_freeze_raises(tmp_path, git_repo):
    """case 2: spec 未 commit → freeze_spec 抛 RuntimeError。"""
    spec = git_repo / "spec.md"
    spec.write_text("modified not committed", encoding="utf-8")
    harness = Harness(
        manifest_dir=tmp_path / "manifest",
        repo_root=git_repo,
    )
    with pytest.raises(RuntimeError, match="未 commit"):
        harness.freeze_spec(spec)


def test_case3_spec_frozen_allows_edit(tmp_path, git_repo):
    """case 3: spec commit + freeze → edit_file 放行。"""
    harness = Harness(
        manifest_dir=tmp_path / "manifest",
        repo_root=git_repo,
    )
    sha = harness.freeze_spec(git_repo / "spec.md")
    assert harness.spec_frozen
    assert sha is not None

    result = harness.check_tool_permission(SDLCPhase.CODING, "edit_file")
    assert result.allowed is True
    assert result.danger_level == DangerLevel.L1


def test_case4_manifest_write_needs_revalidation(tmp_path, git_repo):
    """case 4: manifest 写 needs_revalidation → 读回一致。"""
    harness = Harness(
        manifest_dir=tmp_path / "manifest",
        repo_root=git_repo,
    )
    harness.freeze_spec(git_repo / "spec.md")

    harness.update_manifest_field(
        "phase3",
        "needs_revalidation",
        ["auth/login.go", "session/manager.go"],
    )
    value = harness.get_manifest_field("phase3", "needs_revalidation")
    assert value == ["auth/login.go", "session/manager.go"]


def test_read_only_not_blocked_by_spec_freeze(tmp_path, git_repo):
    """read_file 不受 spec 冻结限制（L0 无害，随时可用）。"""
    harness = Harness(
        manifest_dir=tmp_path / "manifest",
        repo_root=git_repo,
    )
    assert not harness.spec_frozen

    result = harness.check_tool_permission(SDLCPhase.CODING, "read_file")
    assert result.allowed is True


def test_l2_blocked_even_with_spec_frozen(tmp_path, git_repo):
    """L2 工具即使 spec 已冻结仍被拒（权限层先于 spec-first 检查）。"""
    harness = Harness(
        manifest_dir=tmp_path / "manifest",
        repo_root=git_repo,
    )
    harness.freeze_spec(git_repo / "spec.md")

    result = harness.check_tool_permission(
        SDLCPhase.RELEASE, "kubectl_apply"
    )
    assert result.allowed is False
    assert result.danger_level == DangerLevel.L2


def test_testing_phase_write_needs_spec_freeze(tmp_path, git_repo):
    """测试阶段的写操作也需要 spec 冻结（spec-first 覆盖 coding + testing）。"""
    harness = Harness(
        manifest_dir=tmp_path / "manifest",
        repo_root=git_repo,
    )
    # spec 未冻结
    result = harness.check_tool_permission(SDLCPhase.TESTING, "write_file")
    assert result.allowed is False
    assert "未冻结" in result.reason

    # 冻结后放行
    harness.freeze_spec(git_repo / "spec.md")
    result = harness.check_tool_permission(SDLCPhase.TESTING, "write_file")
    assert result.allowed is True
