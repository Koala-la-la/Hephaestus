"""spec 包 — spec 版本锁定。

design doc §7.1。编码入口冻结 spec SHA，后续读按 SHA 读。
"""

from engineering_agent.spec.lock import SpecLock

__all__ = ["SpecLock"]
