"""PromptBuilder 测试。"""

from engineering_agent.manifest.store import ManifestStore
from engineering_agent.prompt.builder import PromptBuilder


def test_build_prompt_coding(tmp_path):
    """编码阶段组装 L1+L2+L3。"""
    store = ManifestStore(tmp_path)
    store.write("common", {"spec_sha": "abc123"})
    result = PromptBuilder().build_prompt("coding", store)
    assert "执行者" in result.l1_identity
    assert "coding" in result.l2_task_spec
    assert "abc123" in result.l2_task_spec
    assert "tool_call" in result.l3_protocol


def test_build_prompt_all_phases(tmp_path):
    """5 阶段各有身份模板。"""
    store = ManifestStore(tmp_path)
    builder = PromptBuilder()
    for phase in ("requirement", "design", "coding", "testing", "release"):
        result = builder.build_prompt(phase, store)
        assert len(result.l1_identity) > 0
        assert len(result.l3_protocol) > 0


def test_l2_reads_tasks(tmp_path):
    """L2 从 manifest 读 task_spec。"""
    store = ManifestStore(tmp_path)
    store.write("common", {"spec_sha": "sha-v3"})
    store.write("phase2", {"tasks": [
        {"id": "T-1", "status": "pending", "spec_refs": ["4.2"]},
    ]})
    result = PromptBuilder().build_prompt("coding", store)
    assert "T-1" in result.l2_task_spec
    assert "4.2" in result.l2_task_spec


def test_l2_reads_needs_revalidation(tmp_path):
    """L2 读 needs_revalidation。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"needs_revalidation": ["auth/login.go"]})
    result = PromptBuilder().build_prompt("coding", store)
    assert "auth/login.go" in result.l2_task_spec


def test_l1_unknown_phase_empty():
    """未知阶段 L1 为空。"""
    assert PromptBuilder().get_l1("unknown") == ""
