"""FeedbackKeeper 测试。"""

from engineering_agent.context.feedback import FeedbackKeeper


def test_set_get():
    keeper = FeedbackKeeper()
    keeper.set("lint", "0 warnings")
    assert keeper.get("lint") == "0 warnings"


def test_set_overwrites_not_accumulates():
    """set 覆盖旧值不累积（§10.3 核心行为）。"""
    keeper = FeedbackKeeper()
    keeper.set("lint", "5 warnings")
    keeper.set("lint", "0 warnings")
    assert keeper.get("lint") == "0 warnings"


def test_get_missing():
    keeper = FeedbackKeeper()
    assert keeper.get("nonexistent") is None


def test_clear():
    keeper = FeedbackKeeper()
    keeper.set("lint", "ok")
    keeper.set("compile", "pass")
    keeper.clear("lint")
    assert keeper.get("lint") is None
    assert keeper.get("compile") == "pass"


def test_clear_all():
    keeper = FeedbackKeeper()
    keeper.set("lint", "ok")
    keeper.set("compile", "pass")
    keeper.clear_all()
    assert keeper.keys() == []


def test_keys():
    keeper = FeedbackKeeper()
    keeper.set("lint", "ok")
    keeper.set("compile", "pass")
    assert set(keeper.keys()) == {"lint", "compile"}
