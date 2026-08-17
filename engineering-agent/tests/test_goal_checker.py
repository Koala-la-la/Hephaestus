"""CriticGoalChecker 测试。"""

from engineering_agent.graph.goal_checker import CriticGoalChecker


def test_measurable_with_comparison():
    """含比较运算符+数字 → True。"""
    c = CriticGoalChecker()
    assert c.machine_check("P99 < 200ms") is True
    assert c.machine_check("错误率 <= 0.1%") is True
    assert c.machine_check("QPS > 1000") is True


def test_measurable_with_number_unit():
    """含数字+单位但无比较符 → True。"""
    c = CriticGoalChecker()
    assert c.machine_check("延迟 200ms 以内") is True
    assert c.machine_check("支持 1000 QPS") is True


def test_not_measurable():
    """无量化指标 → False。"""
    c = CriticGoalChecker()
    assert c.machine_check("性能要好") is False
    assert c.machine_check("提升用户体验") is False
    assert c.machine_check("代码质量高") is False


def test_empty_goal():
    """空目标 → False。"""
    assert CriticGoalChecker().machine_check("") is False


def test_critic_check_fallback():
    """Critic 精判本轮回退到机器粗筛。"""
    c = CriticGoalChecker()
    assert c.critic_check("P99 < 200ms") is True
    assert c.critic_check("性能要好") is False
