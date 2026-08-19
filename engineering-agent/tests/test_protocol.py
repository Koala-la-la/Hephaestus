"""L3Protocol 测试。"""

import json

import pytest

from engineering_agent.prompt.protocol import (
    L3Protocol,
    StepOutput,
    TaskComplete,
    ToolCall,
)


def test_parse_tool_call():
    """解析 tool_call。"""
    result = L3Protocol.parse_output(
        '{"type":"tool_call","tool":"edit_file","args":{"path":"a.go"}}'
    )
    assert isinstance(result, ToolCall)
    assert result.tool == "edit_file"
    assert result.args["path"] == "a.go"


def test_parse_step_output():
    """解析 step_output。"""
    result = L3Protocol.parse_output(
        '{"type":"step_output","action":"edit_file","input":{"path":"a.go"},'
        '"output":{"status":"success"},"duration":30,'
        '"manifest_update_request":{"phase3.needs_revalidation":["a.go"]}}'
    )
    assert isinstance(result, StepOutput)
    assert result.action == "edit_file"
    assert result.duration == 30
    assert "phase3.needs_revalidation" in result.manifest_update_request


def test_parse_task_complete():
    """解析 task_complete。"""
    result = L3Protocol.parse_output(
        '{"type":"task_complete","id":"T-3","evidence":{"compile_passed":true}}'
    )
    assert isinstance(result, TaskComplete)
    assert result.id == "T-3"
    assert result.evidence["compile_passed"] is True


def test_parse_unknown_type_raises():
    """未知 type 抛 ValueError。"""
    with pytest.raises(ValueError, match="未知输出类型"):
        L3Protocol.parse_output('{"type":"unknown","foo":"bar"}')


def test_parse_invalid_json_raises():
    """无效 JSON 抛异常。"""
    with pytest.raises(json.JSONDecodeError):
        L3Protocol.parse_output("not json")
