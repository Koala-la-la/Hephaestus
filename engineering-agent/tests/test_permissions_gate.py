"""工具权限拦截器测试。

验收标准（spec.md Task 5）：L0 放行 / L2 拒绝 / L3 need_confirm + audit 日志验证。
"""

from engineering_agent.manifest.models import SDLCPhase
from engineering_agent.permissions.gate import ToolGate
from engineering_agent.permissions.levels import DangerLevel


def test_l0_allow_no_audit():
    """L0 放行，不写 audit（无害操作不需要审计）。"""
    gate = ToolGate()
    result = gate.check_permission(SDLCPhase.CODING, "read_file")
    assert result.allowed is True
    assert result.danger_level == DangerLevel.L0
    assert len(gate.audit_log) == 0


def test_l1_allow_with_audit():
    """L1 放行，写 audit 日志。"""
    gate = ToolGate()
    result = gate.check_permission(SDLCPhase.CODING, "edit_file")
    assert result.allowed is True
    assert result.danger_level == DangerLevel.L1
    assert len(gate.audit_log) == 1
    assert gate.audit_log[0]["action"] == "allowed"
    assert gate.audit_log[0]["tool"] == "edit_file"


def test_l2_deny_with_audit():
    """L2 拒绝，写 audit 日志（§6.3 铁律2：Harness 直接禁）。"""
    gate = ToolGate()
    result = gate.check_permission(SDLCPhase.RELEASE, "kubectl_apply")
    assert result.allowed is False
    assert result.danger_level == DangerLevel.L2
    assert len(gate.audit_log) == 1
    assert gate.audit_log[0]["action"] == "denied"


def test_l3_need_confirm():
    """L3 返回 need_confirm，写 audit 日志。"""
    gate = ToolGate()
    result = gate.check_permission(SDLCPhase.RELEASE, "request_confirm")
    assert result.allowed is False
    assert result.danger_level == DangerLevel.L3
    assert result.needs_confirm is True
    assert len(gate.audit_log) == 1
    assert gate.audit_log[0]["action"] == "need_confirm"


def test_audit_log_accumulates():
    """audit 日志累积（L0 不记，L1/L2/L3 各记一条）。"""
    gate = ToolGate()
    gate.check_permission(SDLCPhase.CODING, "read_file")  # L0 不记
    gate.check_permission(SDLCPhase.CODING, "edit_file")  # L1 记
    gate.check_permission(SDLCPhase.RELEASE, "kubectl_apply")  # L2 记
    gate.check_permission(SDLCPhase.RELEASE, "request_confirm")  # L3 记
    assert len(gate.audit_log) == 3


def test_clear_audit_log():
    """清空 audit 日志。"""
    gate = ToolGate()
    gate.check_permission(SDLCPhase.CODING, "edit_file")
    gate.clear_audit_log()
    assert len(gate.audit_log) == 0


def test_requirement_write_denied():
    """需求阶段 write_file 被拒绝（默认 L2）。"""
    gate = ToolGate()
    result = gate.check_permission(SDLCPhase.REQUIREMENT, "write_file")
    assert result.allowed is False
    assert result.danger_level == DangerLevel.L2


def test_audit_log_entry_fields():
    """audit 日志条目包含完整字段。"""
    gate = ToolGate()
    gate.check_permission(SDLCPhase.CODING, "run_test")
    entry = gate.audit_log[0]
    assert "phase" in entry
    assert "tool" in entry
    assert "level" in entry
    assert "action" in entry
    assert "reason" in entry
    assert entry["phase"] == "coding"
    assert entry["tool"] == "run_test"
    assert entry["level"] == "L1"
