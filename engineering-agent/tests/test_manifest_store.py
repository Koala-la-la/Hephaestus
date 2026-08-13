"""manifest 读写器 + 归档/恢复测试。

验收标准（spec.md Task 3）：读写往返 + 归档/恢复一致。
"""

import pytest

from engineering_agent.manifest.archive import archive_manifest, restore_manifest
from engineering_agent.manifest.models import ChangeType, CommonManifest
from engineering_agent.manifest.store import ManifestStore


def test_write_read_roundtrip(tmp_path):
    """dict 写入 → 读取 往返一致。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"compile_passed": True, "lint_baseline_delta": 0})
    data = store.read("phase3")
    assert data["compile_passed"] is True
    assert data["lint_baseline_delta"] == 0


def test_write_model_read_model(tmp_path):
    """Pydantic 模型写入 → 模型读取 往返一致。"""
    store = ManifestStore(tmp_path)
    model = CommonManifest(
        spec_sha="abc123",
        spec_version="v3",
        change_type=ChangeType.MINOR,
    )
    store.write_model("common", model)
    m2 = store.read_model("common")
    assert m2 is not None
    assert m2.spec_sha == "abc123"
    assert m2.change_type == ChangeType.MINOR


def test_get_field(tmp_path):
    """get_field 读特定字段。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"compile_passed": True, "review_passed": False})
    assert store.get_field("phase3", "compile_passed") is True
    assert store.get_field("phase3", "review_passed") is False
    assert store.get_field("phase3", "nonexistent") is None


def test_update_field(tmp_path):
    """update_field 更新特定字段（read-modify-write）。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"compile_passed": False})
    store.update_field("phase3", "compile_passed", True)
    assert store.get_field("phase3", "compile_passed") is True


def test_update_field_preserves_other_fields(tmp_path):
    """update_field 不影响同片其他字段。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"compile_passed": False, "review_passed": False})
    store.update_field("phase3", "compile_passed", True)
    assert store.get_field("phase3", "compile_passed") is True
    assert store.get_field("phase3", "review_passed") is False


def test_read_nonexistent(tmp_path):
    """文件不存在返回空 dict / None。"""
    store = ManifestStore(tmp_path)
    assert store.read("phase3") == {}
    assert store.read_model("phase3") is None


def test_read_all(tmp_path):
    """read_all 只返回存在的片。"""
    store = ManifestStore(tmp_path)
    store.write("common", {"spec_sha": "abc"})
    store.write("phase3", {"compile_passed": True})
    all_phases = store.read_all()
    assert "common" in all_phases
    assert "phase3" in all_phases
    assert "phase1" not in all_phases


def test_invalid_phase_raises(tmp_path):
    """未知片名抛 ValueError。"""
    store = ManifestStore(tmp_path)
    with pytest.raises(ValueError, match="未知 manifest 片"):
        store.read("phase99")


def test_archive_restore(tmp_path):
    """归档 → 修改 → 恢复 一致。"""
    store = ManifestStore(tmp_path)
    store.write_model(
        "common",
        CommonManifest(spec_sha="sha-v3", spec_version="v3"),
    )
    store.write("phase3", {"compile_passed": True})

    # 归档 v3
    archive_path = archive_manifest(store, "v3")
    assert archive_path.exists()
    assert archive_path.name == "manifest.v3.json"

    # 修改（模拟 major 刷新后的变化）
    store.update_field("phase3", "compile_passed", False)
    assert store.get_field("phase3", "compile_passed") is False

    # 恢复 v3
    restore_manifest(store, "v3")
    assert store.get_field("phase3", "compile_passed") is True
    common = store.read_model("common")
    assert common is not None
    assert common.spec_sha == "sha-v3"


def test_restore_nonexistent_archive(tmp_path):
    """恢复不存在的归档抛 FileNotFoundError。"""
    store = ManifestStore(tmp_path)
    with pytest.raises(FileNotFoundError, match="归档不存在"):
        restore_manifest(store, "v999")


def test_archive_preserves_old(tmp_path):
    """归档不删除当前 manifest（旧 manifest 仍在）。"""
    store = ManifestStore(tmp_path)
    store.write("phase3", {"compile_passed": True})
    archive_manifest(store, "v3")
    # 当前 manifest 仍在
    assert store.get_field("phase3", "compile_passed") is True
