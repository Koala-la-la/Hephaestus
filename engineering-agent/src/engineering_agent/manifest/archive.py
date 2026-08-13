"""manifest 归档与恢复。

design doc §5.4 版本一致性规则：
- major 刷新时整体归档到 archives/manifest.<version>.json
- 回滚时从归档恢复
- 旧 manifest 不删，以备审计和回滚锚点
"""

from __future__ import annotations

import json
from pathlib import Path

from engineering_agent.manifest.store import ManifestStore, PHASE_MODELS

# 归档文件里存版本号的字段名（恢复时移除，不写入分片）
_ARCHIVE_VERSION_KEY = "_archive_version"


def archive_manifest(store: ManifestStore, version: str) -> Path:
    """major 刷新时整体归档。

    合并六片为一个 JSON 快照，存到 archives/manifest.<version>.json。
    旧 manifest 不删——以备审计和回滚（design doc §5.4）。

    Args:
        store: ManifestStore 实例
        version: spec 版本号（如 "v3"）

    Returns:
        归档文件路径
    """
    store.archives_dir.mkdir(parents=True, exist_ok=True)
    snapshot = store.read_all()
    snapshot[_ARCHIVE_VERSION_KEY] = version
    archive_path = store.archives_dir / f"manifest.{version}.json"
    archive_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return archive_path


def restore_manifest(store: ManifestStore, version: str) -> None:
    """从归档恢复六片 manifest。

    回滚到指定版本时，从 archives/manifest.<version>.json 恢复所有片。
    当前 manifest 被覆盖（design doc §5.4 回滚恢复）。

    Args:
        store: ManifestStore 实例
        version: 要恢复的 spec 版本号（如 "v3"）

    Raises:
        FileNotFoundError: 归档文件不存在
    """
    archive_path = store.archives_dir / f"manifest.{version}.json"
    if not archive_path.exists():
        raise FileNotFoundError(f"归档不存在: {archive_path}")

    snapshot = json.loads(archive_path.read_text(encoding="utf-8"))
    snapshot.pop(_ARCHIVE_VERSION_KEY, None)

    # 恢复归档中存在的每一片
    for phase in PHASE_MODELS:
        if phase in snapshot:
            store.write(phase, snapshot[phase])
