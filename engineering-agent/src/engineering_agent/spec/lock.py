"""spec SHA 锁定。

design doc §7.1。编码入口冻结 spec 的 Git commit SHA，后续读按 SHA 读——
agent 不会读到 v4 还以为是 v3（版本一致性）。

spec 每次升版本必须 commit，否则 SHA 锁不住（§7.1 强制 commit）。
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class SpecLock:
    """spec SHA 锁定器。

    freeze → 记录当前 commit SHA（spec 版本 = commit 版本，§7.1）
    read_locked → 按 SHA 读指定 commit 中的 spec 内容（不串版本）
    check_committed → 检查 spec 是否已 commit（未 commit 无法锁定）
    """

    def __init__(self, repo_root: Path | str | None = None) -> None:
        self._repo_root = Path(repo_root) if repo_root else None

    def _run_git(
        self, args: list[str], cwd: Path | None = None
    ) -> str:
        """运行 git 命令，返回 stdout（已 strip）。

        Raises:
            RuntimeError: git 命令失败
        """
        result = subprocess.run(
            ["git", *args],
            cwd=cwd or self._repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {args[0]} 失败: {result.stderr.strip()}"
            )
        return result.stdout.strip()

    def check_committed(self, spec_path: Path | str) -> bool:
        """检查 spec 文件是否已 commit 且无未提交变更。

        未 commit 的 spec 无法锁定 SHA（§7.1 强制 commit）。
        """
        path = Path(spec_path)
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", str(path)],
            cwd=self._repo_root or path.parent,
            capture_output=True,
            text=True,
        )
        # 输出为空 = 文件已 commit 且无变更
        return result.stdout.strip() == ""

    def freeze(self, spec_path: Path | str) -> str:
        """冻结 spec 的当前 Git commit SHA。

        Args:
            spec_path: spec.md 的路径

        Returns:
            commit SHA（如 "727dd9c..."）

        Raises:
            RuntimeError: spec 未 commit（无法锁定，§7.1 强制 commit）
        """
        path = Path(spec_path)
        if not self.check_committed(path):
            raise RuntimeError(
                "spec 未 commit，无法锁定 SHA"
                "（design doc §7.1：spec 升版本必须 commit）"
            )
        # 返回当前 commit SHA（spec 版本 = commit 版本）
        return self._run_git(["rev-parse", "HEAD"], cwd=path.parent)

    def read_locked(self, spec_path: Path | str, sha: str) -> str:
        """按指定 commit SHA 读 spec 内容。

        用 git show <sha>:<path> 读指定 commit 中的文件——
        即使工作区的 spec 已改成 v4，read_locked 仍返回冻结版本的内容。
        """
        path = Path(spec_path)
        relative = self._get_relative_path(path)
        return self._run_git(
            ["show", f"{sha}:{relative}"], cwd=path.parent
        )

    def _get_relative_path(self, path: Path) -> str:
        """获取文件相对仓库根的路径（git 要求用 / 分隔）。"""
        if self._repo_root:
            relative = str(
                path.resolve().relative_to(self._repo_root.resolve())
            )
        else:
            toplevel = self._run_git(
                ["rev-parse", "--show-toplevel"], cwd=path.parent
            )
            relative = str(
                path.resolve().relative_to(Path(toplevel).resolve())
            )
        # git 路径用 / 分隔（Windows 下需要转换）
        return relative.replace("\\", "/")
