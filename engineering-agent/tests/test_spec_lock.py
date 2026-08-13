"""spec SHA 锁定测试。

验收标准（spec.md Task 6）：freeze + read_locked + 未 commit 拒绝。
用临时 git 仓库测试（git_repo fixture）。
"""

import subprocess

import pytest

from engineering_agent.spec.lock import SpecLock


@pytest.fixture
def git_repo(tmp_path):
    """创建临时 git 仓库，含一个已 commit 的 spec.md（v1）。"""
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


def test_check_committed_true(git_repo):
    """已 commit 的文件返回 True。"""
    lock = SpecLock(git_repo)
    assert lock.check_committed(git_repo / "spec.md") is True


def test_check_committed_false_modified(git_repo):
    """已修改未 commit 的文件返回 False。"""
    spec = git_repo / "spec.md"
    spec.write_text("# Spec\n\nv2 content", encoding="utf-8")
    lock = SpecLock(git_repo)
    assert lock.check_committed(spec) is False


def test_check_committed_false_untracked(tmp_path):
    """未跟踪的文件返回 False。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    spec = repo / "spec.md"
    spec.write_text("untracked", encoding="utf-8")
    lock = SpecLock(repo)
    assert lock.check_committed(spec) is False


def test_freeze_returns_sha(git_repo):
    """freeze 返回非空 SHA 字符串。"""
    lock = SpecLock(git_repo)
    sha = lock.freeze(git_repo / "spec.md")
    assert isinstance(sha, str)
    assert len(sha) > 0


def test_freeze_uncommitted_raises(git_repo):
    """freeze 未 commit 的文件抛 RuntimeError。"""
    spec = git_repo / "spec.md"
    spec.write_text("modified not committed", encoding="utf-8")
    lock = SpecLock(git_repo)
    with pytest.raises(RuntimeError, match="未 commit"):
        lock.freeze(spec)


def test_read_locked_returns_content(git_repo):
    """read_locked 按 SHA 读 spec 内容。"""
    lock = SpecLock(git_repo)
    sha = lock.freeze(git_repo / "spec.md")
    content = lock.read_locked(git_repo / "spec.md", sha)
    assert "v1 content" in content


def test_read_locked_unchanged_after_modify(git_repo):
    """修改 spec 并 commit 新版本后，read_locked 仍返回冻结版本内容（不串版本）。"""
    lock = SpecLock(git_repo)
    sha = lock.freeze(git_repo / "spec.md")

    # 修改并 commit v2
    spec = git_repo / "spec.md"
    spec.write_text("# Spec\n\nv2 content", encoding="utf-8")
    subprocess.run(["git", "add", "spec.md"], cwd=git_repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "v2"], cwd=git_repo, capture_output=True
    )

    # read_locked 仍返回 v1（冻结版本）
    content = lock.read_locked(spec, sha)
    assert "v1 content" in content
    assert "v2 content" not in content
