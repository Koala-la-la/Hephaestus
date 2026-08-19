"""Prompt 层集成验证测试。"""

from engineering_agent.manifest.store import ManifestStore
from engineering_agent.prompt.builder import PromptBuilder
from engineering_agent.prompt.confirm import (
    ConfirmManager,
    ConfirmRequest,
    ConfirmType,
)
from engineering_agent.prompt.protocol import (
    L3Protocol,
    TaskComplete,
    ToolCall,
)


def test_case1_prompt_builder(tmp_path):
    """case 1: PromptBuilder 组装三子层。"""
    store = ManifestStore(tmp_path)
    store.write("common", {"spec_sha": "abc"})
    store.write("phase2", {"tasks": [{"id": "T-1", "status": "pending", "spec_refs": ["4.2"]}]})
    result = PromptBuilder().build_prompt("coding", store)
    assert "执行者" in result.l1_identity
    assert "T-1" in result.l2_task_spec
    assert "tool_call" in result.l3_protocol


def test_case2_protocol_parse():
    """case 2: L3Protocol 解析三种输出。"""
    tc = L3Protocol.parse_output('{"type":"tool_call","tool":"read_file","args":{}}')
    assert isinstance(tc, ToolCall)
    tcl = L3Protocol.parse_output('{"type":"task_complete","id":"T-1","evidence":{}}')
    assert isinstance(tcl, TaskComplete)


def test_case3_confirm_priority():
    """case 3: 覆盖确认优先于阶段出口。"""
    mgr = ConfirmManager()
    mgr.request(ConfirmRequest("p1", ConfirmType.PHASE_EXIT, "coding", "阶段出口"))
    mgr.request(ConfirmRequest("o1", ConfirmType.OVERRIDE, "coding", "覆盖 P0"))
    assert mgr.get_pending().request_id == "o1"
    mgr.resolve("o1", True)
    assert mgr.get_pending().request_id == "p1"


def test_case4_full_workflow(tmp_path):
    """case 4: 完整工作流——Prompt 组装 + 协议解析 + 确认管理。"""
    # 1. 组装 Prompt
    store = ManifestStore(tmp_path)
    store.write("common", {"spec_sha": "v3-sha"})
    prompt = PromptBuilder().build_prompt("coding", store)
    assert "v3-sha" in prompt.l2_task_spec

    # 2. 解析 agent 输出
    output = L3Protocol.parse_output(
        '{"type":"task_complete","id":"T-1","evidence":{"compile_passed":true}}'
    )
    assert isinstance(output, TaskComplete)
    assert output.evidence["compile_passed"] is True

    # 3. 确认管理
    mgr = ConfirmManager()
    mgr.request(ConfirmRequest("c1", ConfirmType.PHASE_EXIT, "coding", "T-1 完成"))
    result = mgr.resolve("c1", approved=True)
    assert result.approved is True
