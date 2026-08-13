"""manifest 分片读写器。

design doc §5.1（分片存储）+ §5.5（写入时机原则）。
Harness 的唯一操作对象——Harness 只通过本类操作 manifest，不直接解析文件。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from engineering_agent.manifest.models import (
    CommonManifest,
    Phase1Manifest,
    Phase2Manifest,
    Phase3Manifest,
    Phase4Manifest,
    Phase5Manifest,
)

# 分片名 → Pydantic 模型类
PHASE_MODELS: dict[str, type[BaseModel]] = {
    "common": CommonManifest,
    "phase1": Phase1Manifest,
    "phase2": Phase2Manifest,
    "phase3": Phase3Manifest,
    "phase4": Phase4Manifest,
    "phase5": Phase5Manifest,
}


class ManifestStore:
    """manifest 分片读写器。

    分片存储：common/phase1-5 各一个 JSON 文件（design doc §5.1）。
    Harness 只通过本类操作 manifest，不直接解析文件——
    这是「manifest 是阶段出口唯一凭证」原则的执行点（§5.3 铁律3）。

    update_field 是 Harness 专用——agent 通过 L3 协议的
    manifest_update_request 请求，Harness 校验后用本方法写入（§5.5）。
    """

    def __init__(self, manifest_dir: Path | str) -> None:
        self.manifest_dir = Path(manifest_dir)
        self.archives_dir = self.manifest_dir / "archives"

    def _path(self, phase: str) -> Path:
        """获取分片文件路径。

        Raises:
            ValueError: 未知分片名
        """
        if phase not in PHASE_MODELS:
            raise ValueError(
                f"未知 manifest 片: {phase}，可选: {list(PHASE_MODELS)}"
            )
        return self.manifest_dir / f"{phase}.json"

    def read(self, phase: str) -> dict[str, Any]:
        """读取一片 manifest 为 dict。文件不存在返回空 dict。"""
        path = self._path(phase)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, phase: str, data: dict[str, Any]) -> None:
        """写入一片 manifest（dict）。自动创建父目录。"""
        path = self._path(phase)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def read_model(self, phase: str) -> BaseModel | None:
        """读取一片并返回 Pydantic 模型。文件不存在返回 None。"""
        data = self.read(phase)
        if not data:
            return None
        return PHASE_MODELS[phase].model_validate(data)

    def write_model(self, phase: str, model: BaseModel) -> None:
        """写入 Pydantic 模型。

        用 model_dump(mode="json") 确保枚举等被序列化为字符串值，
        而非 Enum 对象（design doc §5.3 铁律2：字段必须机器可读）。
        """
        data = model.model_dump(mode="json")
        self.write(phase, data)

    def get_field(self, phase: str, field: str) -> Any:
        """读特定片的特定字段。字段不存在返回 None。"""
        return self.read(phase).get(field)

    def update_field(self, phase: str, field: str, value: Any) -> None:
        """更新特定片的特定字段（read-modify-write）。

        Harness 专用——agent 通过 L3 manifest_update_request 请求，
        Harness 校验后用本方法写入（design doc §5.5 写入时机原则）。
        """
        data = self.read(phase)
        data[field] = value
        self.write(phase, data)

    def read_all(self) -> dict[str, dict[str, Any]]:
        """读取所有存在的片（不存在的片不包含在结果中）。"""
        result: dict[str, dict[str, Any]] = {}
        for phase in PHASE_MODELS:
            data = self.read(phase)
            if data:
                result[phase] = data
        return result
