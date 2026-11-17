"""The interface every stock store backend implements.

Backends raise the errors defined in `inventory.store` (NotFound, DuplicateSku,
InsufficientStock); the app turns them into status codes.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from inventory.store import Item


@runtime_checkable
class Store(Protocol):
    """Items by SKU."""

    def list(self, category: str | None = None) -> list[Item]:
        """All items (optionally one category), sorted by SKU."""
        ...

    def get(self, sku: str) -> Item:
        """The item with this SKU. Raises NotFound."""
        ...

    def create(self, item: Item) -> Item:
        """Add an item. Raises DuplicateSku."""
        ...

    def update(self, sku: str, **changes: object) -> Item:
        """Change fields of an item. Raises NotFound."""
        ...

    def delete(self, sku: str) -> None:
        """Remove an item. Raises NotFound."""
        ...

    def adjust(self, sku: str, delta: int) -> Item:
        """Add `delta` (negative to remove) to a quantity.

        Raises NotFound, or InsufficientStock if the quantity would go below zero.
        """
        ...

    def adjust_many(self, adjustments: Iterable[tuple[str, int]]) -> list[Item]:
        """Apply every (sku, delta) adjustment atomically, or none of them.

        A SKU may repeat: the stock check uses the running total. Unknown SKUs
        raise NotFound before any stock check; the first entry that would go
        below zero raises InsufficientStock. Returns the updated items, one per
        distinct SKU, in order of first appearance.
        """
        ...
