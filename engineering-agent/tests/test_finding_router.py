"""FindingRouter 测试。"""

from engineering_agent.graph.finding_router import FindingRouter
from engineering_agent.manifest.models import (
    FindingSeverity,
    FindingSource,
    ReviewFinding,
)


def test_machine_p0_block_not_overridable():
    """机器 P0 → block 不可覆盖。"""
    f = ReviewFinding(severity=FindingSeverity.P0, source=FindingSource.MACHINE, file="a.go")
    assert FindingRouter().route(f).action == "block"
    assert FindingRouter().route(f).overridable is False


def test_agent_p0_block_overridable():
    """agent P0 → block 可覆盖。"""
    f = ReviewFinding(severity=FindingSeverity.P0, source=FindingSource.AGENT, file="b.go")
    assert FindingRouter().route(f).action == "block_overridable"
    assert FindingRouter().route(f).overridable is True


def test_p1_record():
    """P1 → record 不阻断。"""
    f = ReviewFinding(severity=FindingSeverity.P1, source=FindingSource.AGENT, file="c.go")
    assert FindingRouter().route(f).action == "record"


def test_p2_record():
    """P2 → record 不阻断。"""
    f = ReviewFinding(severity=FindingSeverity.P2, source=FindingSource.MACHINE, file="d.go")
    assert FindingRouter().route(f).action == "record"


def test_batch_has_block():
    """批量有阻断项。"""
    findings = [
        ReviewFinding(severity=FindingSeverity.P0, source=FindingSource.MACHINE, file="a.go"),
        ReviewFinding(severity=FindingSeverity.P1, source=FindingSource.AGENT, file="b.go"),
    ]
    result = FindingRouter().route_batch(findings)
    assert result.has_block is True
    assert len(result.blocks) == 1


def test_batch_no_block():
    """批量无阻断项。"""
    findings = [
        ReviewFinding(severity=FindingSeverity.P1, source=FindingSource.AGENT, file="a.go"),
        ReviewFinding(severity=FindingSeverity.P2, source=FindingSource.MACHINE, file="b.go"),
    ]
    result = FindingRouter().route_batch(findings)
    assert result.has_block is False
