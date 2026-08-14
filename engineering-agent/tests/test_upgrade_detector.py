"""UpgradeDetector 测试。

验收标准：占比>阈值升级 / finding 涉及需求章升级 / 连续失败升级 / 三条都不满足不升级。
"""

from engineering_agent.loop.upgrade_detector import UpgradeDetector


def test_ratio_below_threshold():
    """占比低于阈值 → 不升级。"""
    detector = UpgradeDetector(ratio_threshold=0.6)
    needs = list("abcdefghij")  # 10 个
    reviewed = list("abcdefgh")  # 审了 8 个 → 20%
    assert detector.check_ratio(needs, reviewed) is False


def test_ratio_above_threshold():
    """占比超阈值 → 升级。"""
    detector = UpgradeDetector(ratio_threshold=0.6)
    needs = list("abcdefghij")  # 10 个
    reviewed = list("abc")  # 审了 3 个 → 70%
    assert detector.check_ratio(needs, reviewed) is True


def test_ratio_empty_needs():
    """needs_revalidation 为空 → 不升级。"""
    detector = UpgradeDetector()
    assert detector.check_ratio([], []) is False


def test_finding_refs_major_chapter():
    """finding 涉及需求章 1.2 → 升级。"""
    detector = UpgradeDetector()
    assert detector.check_finding_refs({"F-1": ["1.2", "4.3"]}) is True


def test_finding_refs_design_overview():
    """finding 涉及方案概览 4.1 → 升级。"""
    detector = UpgradeDetector()
    assert detector.check_finding_refs({"F-1": ["4.1"]}) is True


def test_finding_refs_minor_only():
    """finding 只涉及非需求章 → 不升级。"""
    detector = UpgradeDetector()
    assert detector.check_finding_refs({"F-1": ["4.2", "5.1"]}) is False


def test_consecutive_failures_below():
    """连续失败轮次低于阈值 → 不升级。"""
    detector = UpgradeDetector(consecutive_failures=2)
    assert detector.check_consecutive_failures(1) is False


def test_consecutive_failures_at():
    """连续失败轮次到阈值 → 升级。"""
    detector = UpgradeDetector(consecutive_failures=2)
    assert detector.check_consecutive_failures(2) is True


def test_detect_no_upgrade():
    """三条都不满足 → 不升级。"""
    detector = UpgradeDetector()
    decision = detector.detect(
        needs_revalidation=["a", "b", "c", "d", "e"],
        reviewed=["a", "b", "c", "d"],  # 20% < 60%
        finding_refs={"F-1": ["4.2"]},  # 非需求章
        consecutive_failures=1,  # < 2
    )
    assert decision.should_upgrade is False
    assert len(decision.reasons) == 0


def test_detect_upgrade_ratio():
    """占比触发升级。"""
    detector = UpgradeDetector()
    decision = detector.detect(
        needs_revalidation=["a", "b", "c"],
        reviewed=[],  # 100%
        finding_refs={},
        consecutive_failures=0,
    )
    assert decision.should_upgrade is True
    assert any("占比" in r for r in decision.reasons)


def test_detect_upgrade_finding_refs():
    """finding refs 触发升级。"""
    detector = UpgradeDetector()
    decision = detector.detect(
        needs_revalidation=["a", "b"],
        reviewed=["a", "b"],  # 0%
        finding_refs={"F-1": ["2.1"]},  # 需求章
        consecutive_failures=0,
    )
    assert decision.should_upgrade is True
    assert any("需求章" in r for r in decision.reasons)


def test_detect_multiple_reasons():
    """多个触发条件 → 多个 reason。"""
    detector = UpgradeDetector()
    decision = detector.detect(
        needs_revalidation=["a", "b"],
        reviewed=[],  # 100%
        finding_refs={"F-1": ["1.1"]},  # 需求章
        consecutive_failures=3,  # > 2
    )
    assert decision.should_upgrade is True
    assert len(decision.reasons) == 3
