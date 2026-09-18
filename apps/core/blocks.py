"""Реестр блоков главной (ARCHITECTURE.md §3.2).

Порядок блока в реестре — значение по умолчанию; фактический порядок/видимость
настраиваются через админку, когда появятся их настройки (сейчас — порядок кода).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Block:
    key: str
    template: str
    order: int


_REGISTRY: dict[str, Block] = {}


def register_block(key: str, template: str, order: int = 50) -> None:
    """Зарегистрировать блок главной. Повторный вызов с тем же key — перезапись."""
    _REGISTRY[key] = Block(key=key, template=template, order=order)


def get_blocks() -> list[Block]:
    """Все зарегистрированные блоки, отсортированные по порядку."""
    return sorted(_REGISTRY.values(), key=lambda b: b.order)
