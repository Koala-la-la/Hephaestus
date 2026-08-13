"""工具权限矩阵测试。

验收标准（spec.md Task 4）：给定（阶段, 工具）能查到危险等级。
"""

import pytest

from engineering_agent.manifest.models import SDLCPhase
from engineering_agent.permissions.levels import DangerLevel
from engineering_agent.permissions.matrix import PermissionMatrix


def test_read_file_l0_in_all_phases():
    """read_file 在所有阶段都是 L0。"""
    matrix = PermissionMatrix()
    for phase in SDLCPhase:
        assert matrix.get_level(phase, "read_file") == DangerLevel.L0


def test_coding_edit_file_l1():
    """编码阶段 edit_file 是 L1。"""
    matrix = PermissionMatrix()
    assert matrix.get_level(SDLCPhase.CODING, "edit_file") == DangerLevel.L1


def test_release_kubectl_l2():
    """上线阶段 kubectl 是 L2（未列出默认 L2）。"""
    matrix = PermissionMatrix()
    assert matrix.get_level(SDLCPhase.RELEASE, "kubectl_apply") == DangerLevel.L2


def test_release_request_confirm_l3():
    """上线阶段 request_confirm 是 L3。"""
    matrix = PermissionMatrix()
    assert matrix.get_level(SDLCPhase.RELEASE, "request_confirm") == DangerLevel.L3


def test_requirement_no_write():
    """需求阶段没有写权限（write_file 不在矩阵 → 默认 L2）。"""
    matrix = PermissionMatrix()
    assert matrix.get_level(SDLCPhase.REQUIREMENT, "write_file") == DangerLevel.L2


def test_default_l2_for_unknown_tool():
    """未知工具默认 L2。"""
    matrix = PermissionMatrix()
    assert matrix.get_level(SDLCPhase.CODING, "unknown_tool") == DangerLevel.L2


def test_set_level_override():
    """set_level 可覆盖默认。"""
    matrix = PermissionMatrix()
    matrix.set_level(SDLCPhase.RELEASE, "write_file", DangerLevel.L1)
    assert matrix.get_level(SDLCPhase.RELEASE, "write_file") == DangerLevel.L1


def test_from_to_dict_roundtrip():
    """from_dict / to_dict 往返一致。"""
    matrix = PermissionMatrix()
    d = matrix.to_dict()
    matrix2 = PermissionMatrix.from_dict(d)
    assert matrix2.to_dict() == d


def test_phase_isolation():
    """阶段隔离——编码阶段的 write 权限不带到上线阶段（§6.3 铁律1）。"""
    matrix = PermissionMatrix()
    # 编码阶段 write_file = L1
    assert matrix.get_level(SDLCPhase.CODING, "write_file") == DangerLevel.L1
    # 上线阶段 write_file = L2（未列出，默认禁）
    assert matrix.get_level(SDLCPhase.RELEASE, "write_file") == DangerLevel.L2


def test_coding_run_test_l1():
    """编码阶段 run_test 是 L1（本地执行，有 audit）。"""
    matrix = PermissionMatrix()
    assert matrix.get_level(SDLCPhase.CODING, "run_test") == DangerLevel.L1


def test_coding_git_diff_l0():
    """编码阶段 git_diff 是 L0（只读）。"""
    matrix = PermissionMatrix()
    assert matrix.get_level(SDLCPhase.CODING, "git_diff") == DangerLevel.L0
