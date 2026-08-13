"""冒烟测试：验证项目脚手架能正确导入和运行."""

import engineering_agent


def test_version():
    """验证包版本号正确."""
    assert engineering_agent.__version__ == "0.5.0"


def test_import():
    """验证 engineering_agent 包能被导入无报错."""
    assert engineering_agent is not None
