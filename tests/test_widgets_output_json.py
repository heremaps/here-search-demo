###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest
from unittest.mock import Mock, patch
import orjson

from here_search_demo.widgets.output_json import SearchResultJson, SearchResultList
from here_search_demo.entity.response import Response


class TestSearchResultList:
    """Test SearchResultList base class."""

    def test_init_default_values(self):
        """Test SearchResultList initialization with defaults."""
        from ipywidgets import Layout

        widget = SearchResultList()
        assert widget.widget is not None
        assert widget.max_results_number == SearchResultList.default_max_results_count
        assert widget.queue is not None
        # Layout is converted to Layout object by VBox, check properties match
        assert isinstance(widget.layout, Layout)
        for key, value in SearchResultList.default_layout.items():
            assert getattr(widget.layout, key, None) == value or key == "overflow_y"

    def test_init_custom_values(self):
        """Test SearchResultList initialization with custom values."""
        from ipywidgets import Output, Layout

        custom_widget = Output()
        custom_layout = {"width": "500px"}
        widget = SearchResultList(widget=custom_widget, max_results_number=50, layout=custom_layout)

        assert widget.widget is custom_widget
        assert widget.max_results_number == 50
        # Layout is converted to Layout object by VBox
        assert isinstance(widget.layout, Layout)
        assert widget.layout.width == "500px"

    def test_display_not_implemented(self):
        """Test _display raises NotImplementedError."""
        widget = SearchResultList()
        with pytest.raises(NotImplementedError):
            widget._display(Mock())

    def test_modify_not_implemented(self):
        """Test _modify raises NotImplementedError."""
        widget = SearchResultList()
        with pytest.raises(NotImplementedError):
            widget._modify(Mock())

    def test_clear_returns_output(self):
        """Test _clear returns Output widget."""
        from ipywidgets import Output

        widget = SearchResultList()
        cleared = widget._clear()
        assert isinstance(cleared, Output)
        assert cleared.layout == widget.layout


class TestSearchResultJson:
    """Test SearchResultJson widget."""

    def test_init_creates_instance(self):
        """Test SearchResultJson initialization."""
        widget = SearchResultJson()
        assert widget is not None
        assert hasattr(widget, "_pool")
        assert len(widget._pool) == SearchResultJson._pool_size
        assert widget._pool_index == 0

    def test_init_adds_css_class(self):
        """Test SearchResultJson adds search-json-pane CSS class."""
        widget = SearchResultJson()
        # Verify class was added (ipywidgets add_class method)
        assert "search-json-pane" in widget._dom_classes

    @patch("here_search_demo.widgets.output_json.Idisplay")
    def test_init_injects_css_style_once(self, mock_display):
        """Test CSS style is injected only once globally."""
        # Reset the class variable
        SearchResultJson._style_injected = False

        SearchResultJson()
        assert mock_display.called
        call_count_first = mock_display.call_count

        SearchResultJson()
        # Should not call Idisplay again since _style_injected is True
        assert mock_display.call_count == call_count_first

    def test_next_output_cycles_through_pool(self):
        """Test _next_output cycles through pool correctly."""
        widget = SearchResultJson()
        outputs = []

        # Get all outputs from pool (first 19 should increment, 20th recycles)
        for i in range(SearchResultJson._pool_size - 1):
            out = widget._next_output()
            outputs.append(out)
            assert widget._pool_index == i + 1

        # Get 20th output — will trigger recycling
        out = widget._next_output()
        outputs.append(out)
        # After 20 calls: index goes to 20, then recycles, then increments, so index == 1
        assert widget._pool_index == 1

        # Verify all are different objects before recycling
        assert len(set(id(o) for o in outputs)) == SearchResultJson._pool_size

    @patch("here_search_demo.widgets.output_json.IS_BROWSER_RUNTIME", True)
    @patch("here_search_demo.widgets.output_json.ICode")
    def test_display_browser_runtime_with_raw_json(self, mock_icode):
        """Test _display in browser runtime with raw JSON."""
        widget = SearchResultJson()

        response_data = {"items": [{"id": "1", "title": "Test"}]}
        raw_json = orjson.dumps(response_data)

        response = Mock(spec=Response)
        response.raw = raw_json
        response.data = None
        response.x_headers = {"content-type": "application/json"}

        result = widget._display(response)

        from ipywidgets import Output

        assert isinstance(result, Output)
        # Verify ICode was called for JSON rendering
        assert mock_icode.called

    @patch("here_search_demo.widgets.output_json.IS_BROWSER_RUNTIME", False)
    @patch("here_search_demo.widgets.output_json.IJSON")
    def test_display_notebook_runtime_with_data(self, mock_ijson):
        """Test _display in notebook runtime with data object."""
        widget = SearchResultJson()

        response_data = {"items": [{"id": "1", "title": "Test"}]}

        response = Mock(spec=Response)
        response.raw = None
        response.data = response_data
        response.x_headers = {"content-type": "application/json"}

        result = widget._display(response)

        from ipywidgets import Output

        assert isinstance(result, Output)
        # Verify IJSON was called for notebook display
        assert mock_ijson.called

    @patch("here_search_demo.widgets.output_json.IS_BROWSER_RUNTIME", False)
    @patch("here_search_demo.widgets.output_json.IJSON")
    def test_display_injects_vicinity_from_state(self, mock_ijson):
        """Test _display injects _vicinity from state when available."""
        from here_search_demo.widgets.state import SearchState

        state_mock = Mock(spec=SearchState)
        state_mock.items_data_by_rank = {
            0: {"_vicinity": "test vicinity"},
            1: {"_vicinity": "other vicinity"},
        }

        widget = SearchResultJson(state=state_mock)

        response_data = {"items": [{"id": "1", "title": "Item 1"}, {"id": "2", "title": "Item 2"}]}

        response = Mock(spec=Response)
        response.raw = None
        response.data = response_data
        response.x_headers = {}

        result = widget._display(response)

        from ipywidgets import Output

        assert isinstance(result, Output)
        # Verify _vicinity was injected
        assert response_data["items"][0]["_vicinity"] == "test vicinity"
        assert response_data["items"][1]["_vicinity"] == "other vicinity"

    def test_pool_recycling_on_exhaustion(self):
        """Test pool is recycled when exhausted."""
        widget = SearchResultJson()

        # Get all outputs and exhaust the pool
        outputs = []
        for i in range(SearchResultJson._pool_size + 1):
            out = widget._next_output()
            outputs.append(out)

        # After 21 calls: 1-20 cycle through and recycle (index becomes 1), 21st gets pool[1] (index becomes 2)
        assert widget._pool_index == 2
        assert len(widget._pool) == SearchResultJson._pool_size

    def test_clear_returns_next_output(self):
        """Test _clear returns next output from pool."""
        widget = SearchResultJson()
        cleared = widget._clear()

        from ipywidgets import Output

        assert isinstance(cleared, Output)
        assert widget._pool_index == 1
