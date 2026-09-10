"""Tests for the Lovelace card resource registration."""

from __future__ import annotations

import pytest

from custom_components.seatemperatures import (
    CARD_FILENAME,
    CARD_URL_PREFIX,
    _async_reconcile_card_resource,
)

NEW_URL = f"{CARD_URL_PREFIX}{CARD_FILENAME}?v=3.3.0"
OLD_URL = f"{CARD_URL_PREFIX}{CARD_FILENAME}?v=3.2.0"


class FakeResources:
    """Stand-in for Home Assistant's ResourceStorageCollection.

    The real collection is loaded lazily: async_items() stays empty until a
    write - or an explicit load - pulls the stored items in.
    """

    def __init__(self, stored: list[dict] | None = None) -> None:
        self._stored = [dict(item) for item in stored or []]
        self._items: list[dict] = []
        self._next_id = len(self._stored)
        self.loaded = False

    async def _async_ensure_loaded(self) -> None:
        if not self.loaded:
            await self.async_load()

    async def async_load(self) -> None:
        self._items = [dict(item) for item in self._stored]
        self.loaded = True

    def async_items(self) -> list[dict]:
        return self._items

    async def async_create_item(self, data: dict) -> dict:
        await self._async_ensure_loaded()
        item = {"id": f"generated{self._next_id}", **data}
        self._next_id += 1
        self._items.append(item)
        return item

    async def async_update_item(self, item_id: str, updates: dict) -> dict:
        await self._async_ensure_loaded()
        item = next(item for item in self._items if item["id"] == item_id)
        item.update(updates)
        return item

    async def async_delete_item(self, item_id: str) -> None:
        await self._async_ensure_loaded()
        self._items = [item for item in self._items if item["id"] != item_id]


async def test_registers_the_card_on_a_fresh_install() -> None:
    """Without a resource for our bundle, exactly one is created."""
    resources = FakeResources()

    await _async_reconcile_card_resource(resources, NEW_URL)

    assert [item["url"] for item in resources.async_items()] == [NEW_URL]


async def test_does_not_add_a_second_resource_on_restart() -> None:
    """Regression: the store is empty until loaded, so our own entry was missed.

    Every restart appended another resource, the browser loaded the bundle twice
    and the second copy died on an already registered element name.
    """
    resources = FakeResources(
        [
            {
                "id": "existing",
                "res_type": "module",
                "url": f"{CARD_URL_PREFIX}{CARD_FILENAME}?v=3.2.0",
            }
        ]
    )

    await _async_reconcile_card_resource(resources, NEW_URL)

    assert [item["url"] for item in resources.async_items()] == [NEW_URL]
    assert resources.async_items()[0]["id"] == "existing"


async def test_removes_duplicates_left_by_earlier_versions() -> None:
    """An install that already collected duplicates is cleaned up on setup."""
    resources = FakeResources(
        [
            {
                "id": "one",
                "res_type": "module",
                "url": f"{CARD_URL_PREFIX}{CARD_FILENAME}?v=3.0.0",
            },
            {
                "id": "two",
                "res_type": "module",
                "url": f"{CARD_URL_PREFIX}{CARD_FILENAME}?v=3.1.0",
            },
            {
                "id": "three",
                "res_type": "module",
                "url": f"{CARD_URL_PREFIX}{CARD_FILENAME}?v=3.2.0",
            },
        ]
    )

    await _async_reconcile_card_resource(resources, NEW_URL)

    assert [item["url"] for item in resources.async_items()] == [NEW_URL]


async def test_leaves_unrelated_resources_alone() -> None:
    """Deleting somebody else's resource would be far worse than a leftover."""
    other = {
        "id": "other",
        "res_type": "module",
        "url": "/hacsfiles/other-card/other-card.js",
    }
    resources = FakeResources([dict(other)])

    await _async_reconcile_card_resource(resources, NEW_URL)

    urls = [item["url"] for item in resources.async_items()]
    assert other["url"] in urls
    assert NEW_URL in urls
    assert len(urls) == 2


class UnloadableResources(FakeResources):
    """A store that cannot be read - registering blindly would lose the rest."""

    async def async_load(self) -> None:
        raise RuntimeError("storage unavailable")


async def test_does_not_register_when_the_store_cannot_be_loaded() -> None:
    """A failed load must abort, not fall through to creating a resource.

    Creating one off an empty item list would save a store holding only our own
    resource, dropping every other card's. The caller logs and moves on.
    """
    resources = UnloadableResources(
        [
            {
                "id": "other",
                "res_type": "module",
                "url": "/hacsfiles/other-card/other-card.js",
            }
        ]
    )

    with pytest.raises(RuntimeError):
        await _async_reconcile_card_resource(resources, NEW_URL)

    assert resources.async_items() == []


async def test_loads_a_store_that_does_not_expose_the_loaded_flag() -> None:
    """Without the flag we must still load, not assume the store is ready."""
    resources = FakeResources(
        [{"id": "existing", "res_type": "module", "url": OLD_URL}]
    )
    del resources.loaded

    await _async_reconcile_card_resource(resources, NEW_URL)

    assert [item["url"] for item in resources.async_items()] == [NEW_URL]
    assert resources.async_items()[0]["id"] == "existing"
