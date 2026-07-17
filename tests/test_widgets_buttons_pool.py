###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Test button pool pre-allocation and async replenishment."""

from unittest.mock import MagicMock

import pytest

from here_search_demo.entity.response import Response
from here_search_demo.widgets.output_buttons import SearchResultButtons


@pytest.fixture
def mock_response():
    """Create a mock Response with test data."""
    resp = MagicMock(spec=Response)
    resp.req = MagicMock()
    resp.req.endpoint = None
    resp.data = {"items": []}
    return resp


def test_pool_config_class_attributes():
    """Verify pool configuration is set at class level."""
    assert SearchResultButtons.default_button_pool_size == 200
    assert SearchResultButtons.default_button_pool_chunk_size == 50
    assert SearchResultButtons.default_button_pool_replenish_at == 0.1
    assert "submitted_text" in SearchResultButtons._collapse_intent_kinds
    assert "taxonomy" in SearchResultButtons._collapse_intent_kinds
    assert "transient_text" not in SearchResultButtons._collapse_intent_kinds  # Key change: preserved on typing


def test_expansion_preserved_on_transient():
    """Verify _collapse_intent_kinds excludes transient_text (preserves expansion during typing)."""
    # This is the key behavioral change: transient_text no longer clears expansion
    assert "transient_text" not in SearchResultButtons._collapse_intent_kinds
    assert "submitted_text" in SearchResultButtons._collapse_intent_kinds
    assert "taxonomy" in SearchResultButtons._collapse_intent_kinds


@pytest.mark.asyncio
async def test_replenish_pool_async():
    """Test async replenishment method creates buttons without blocking."""
    # Create widget with minimal initialization
    buttons_widget = SearchResultButtons()
    initial_count = len(buttons_widget.buttons)

    # Verify pool was pre-allocated
    assert initial_count == 200

    # Test replenishment
    await buttons_widget._replenish_pool_async(chunk_size=30)

    # Pool should have grown
    assert len(buttons_widget.buttons) == initial_count + 30
    assert not buttons_widget._replenish_in_progress


@pytest.mark.asyncio
async def test_check_replenish_threshold():
    """Test replenish trigger condition."""
    buttons_widget = SearchResultButtons()

    # Simulate pool near exhaustion by reducing count
    buttons_widget.buttons = buttons_widget.buttons[:15]  # Leave only 15
    replenish_threshold = buttons_widget._replenish_threshold  # Should be 20 (10% of 200)

    # Verify threshold check
    assert len(buttons_widget.buttons) < replenish_threshold

    # Trigger replenishment check
    buttons_widget._check_and_trigger_replenish()

    # Task should be scheduled
    assert buttons_widget._replenish_task is not None

    # Wait for completion
    await buttons_widget._replenish_task

    # Pool should be replenished
    assert len(buttons_widget.buttons) >= 15 + SearchResultButtons.default_button_pool_chunk_size


@pytest.mark.asyncio
async def test_ensure_buttons_with_preallocated_pool():
    """Test _ensure_buttons doesn't create when pool is sufficient."""
    buttons_widget = SearchResultButtons()
    initial_count = len(buttons_widget.buttons)

    # Request a small rank (well within pre-allocated pool)
    buttons_widget._ensure_buttons(5)

    # Pool should not grow
    assert len(buttons_widget.buttons) == initial_count


@pytest.mark.asyncio
async def test_ensure_buttons_fallback_on_exhaustion():
    """Test _ensure_buttons falls back to synchronous creation if exhausted."""
    buttons_widget = SearchResultButtons()

    # Reduce pool to minimal
    buttons_widget.buttons = buttons_widget.buttons[:2]

    # Request a rank beyond current pool but within _max (default 20)
    buttons_widget._ensure_buttons(15)

    # Pool should grow to at least 16 (to cover rank 15)
    assert len(buttons_widget.buttons) >= 16


def test_pool_eliminates_per_search_cost():
    """Validate that pool pre-allocation strategy eliminates per-search button creation cost.

    Cost-benefit:
    - One-time: ~1.3s at startup (200 buttons × ~6.5ms each)
    - Per search: 0ms (buttons already allocated)

    Break-even: After ~500 searches (1300ms / 2.7ms per search)
    """
    buttons_widget = SearchResultButtons()

    # Pool is initialized
    assert len(buttons_widget.buttons) == 200

    # Multiple _ensure_buttons calls don't create
    for _ in range(100):
        buttons_widget._ensure_buttons(5)

    # Pool remains unchanged (no per-search cost)
    assert len(buttons_widget.buttons) == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
