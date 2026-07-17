###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
import time
from collections.abc import Callable
from time import perf_counter_ns

from IPython.display import display as Idisplay
from ipywidgets import HTML, Button, HBox, Label, Layout, VBox, Widget

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.intent import ActionIntent, SearchIntent
from here_search_demo.entity.response import LocationResponseItem, Response
from here_search_demo.widgets.state import SearchState

from .output_details import ResultDetailsBox


class DebouncedButton(Button):
    # Used against https://github.com/jupyter-widgets/ipywidgets/issues/3996
    _debounce_interval: float
    _last_click_time: float
    _click_lock: asyncio.Lock
    _actual_handler: callable

    default_debounce_ms = 250
    default_layout = {
        "width": "95%",
        "justify_content": "flex-start",
        "display": "flex",
    }

    def __init__(self, *args, debounce_ms: int | None = None, **kwargs):
        super().__init__(*args, layout=Layout(**DebouncedButton.default_layout), **kwargs)
        self._debounce_interval = (debounce_ms or self.default_debounce_ms) / 1000
        self._last_click_time = 0.0
        self._click_lock = asyncio.Lock()
        self._actual_handler = None

    def set_handler(self, handler: callable):
        self._actual_handler = handler
        self._click_handlers.callbacks.clear()
        self.on_click(self._safe_click_handler)

    def _safe_click_handler(self, button: Button):
        asyncio.create_task(self._debounced_call(button))

    async def _debounced_call(self, button: Button):
        async with self._click_lock:
            now = time.monotonic()
            if now - self._last_click_time < self._debounce_interval:
                # debounced click
                return
            self._last_click_time = now

        if self._actual_handler:
            if asyncio.iscoroutinefunction(self._actual_handler):
                await self._actual_handler(button)
            else:
                self._actual_handler(button)


class SearchResultButton(DebouncedButton):
    def __init__(self, queue: asyncio.Queue, **kwargs):
        kwargs = kwargs.pop("layout", {})
        DebouncedButton.__init__(self, **kwargs)
        self.rank: int | None = None  # plain attribute — no traitlet overhead

    def set_metadata(self, rank: int, icon: str, description: str):
        if self.rank != rank:
            self.rank = rank
        if self.icon != icon:
            self.icon = icon
        if self.description != description:
            self.description = description


class SearchResultButtonBox(HBox):
    queue: asyncio.Queue
    default_layout = {"width": "100%", "min_width": "0"}

    def __init__(
        self,
        queue: asyncio.Queue,
        state: SearchState,
        on_result_click: Callable[[int], None] | None = None,
        **kvargs,
    ):
        self.queue = queue
        self.state = state
        self.on_result_click = on_result_click
        self.label = Label(value="", layout={"width": "20px"})
        self.button = SearchResultButton(queue)
        self.button_box = VBox(children=[self.button], layout=Layout(**self.default_layout))
        HBox.__init__(
            self,
            [self.label, self.button_box],
            layout=Layout(**kvargs.pop("layout", self.default_layout), overflow="visible"),
            **kvargs,
        )
        self.add_class("result-button")
        self._current_expanded = False
        self._last_item_id: int | None = None  # dirty-check: skip render when item unchanged
        self.button.set_handler(self.handle_click)

    def handle_click(self, button: "SearchResultButton") -> None:
        rank = button.rank
        if rank is None:
            return
        item = self.state.get_item(rank)
        if item is None:
            return
        if isinstance(item, LocationResponseItem):
            if rank in self.state.expanded_ranks:
                self.state.expanded_ranks.remove(rank)
                self.button_box.children = [self.button]
                self._current_expanded = False
            else:
                self.state.expanded_ranks.add(rank)
                details = ResultDetailsBox(item.data)
                self.button_box.children = [self.button, details]
                self._current_expanded = True
                intent = ActionIntent(materialization=item, time=time.perf_counter_ns())
                self.queue.put_nowait(intent)
                if self.on_result_click is not None:
                    self.on_result_click(rank)
        else:
            intent = SearchIntent(kind="details", materialization=item, time=time.perf_counter_ns())
            self.queue.put_nowait(intent)

    def render(self, rank: int, force: bool = False) -> bool:
        item = self.state.get_item(rank)
        if not item:
            return False
        item_id = id(item)  # hydrate() always builds new objects, so this detects stale renders
        expanded = rank in self.state.expanded_ranks
        if not force and item_id == self._last_item_id and expanded == self._current_expanded:
            return False
        self._last_item_id = item_id
        new_label = f"{rank + 1: <2}"
        if self.label.value != new_label:
            self.label.value = new_label
        icon = self.state.icon_for(rank)
        description = self.state.title_for(rank)
        self.button.set_metadata(rank=rank, icon=icon, description=description)
        if expanded != self._current_expanded:
            self._current_expanded = expanded
            if expanded:
                details = ResultDetailsBox(item.data)
                self.button_box.children = [self.button, details]
            else:
                self.button_box.children = [self.button]
        return True


class SearchResultButtons(VBox):
    default_layout = dict(max_height="400px", width="290px")
    default_overflow_y = "auto"
    default_overflow_x = "hidden"
    default_max_results_count = 20
    default_button_pool_size = 200  # Pre-allocate buttons at init
    default_button_pool_replenish_at = 0.1  # Trigger async replenish when <10% remain
    default_button_pool_chunk_size = 50  # Create buttons in chunks during replenish
    _collapse_intent_kinds = {
        "submitted_text",
        "taxonomy",
    }  # Only clear on explicit intents, preserve on transient_text
    _style_applied = False

    def __init__(
        self,
        widget: Widget | None = None,
        max_results_number: int | None = None,
        queue: asyncio.Queue | None = None,
        state: SearchState | None = None,
        on_result_click: Callable[[int], None] | None = None,
        layout: dict | None = None,
        **kwargs,
    ):
        self.queue = queue or asyncio.Queue()
        self.on_result_click = on_result_click
        self.layout = Layout(**(layout or self.default_layout))
        self.layout.overflow_y = self.default_overflow_y
        self.layout.overflow_x = self.default_overflow_x
        self._inner_box = VBox([], layout=self.layout)
        super().__init__([self._inner_box], layout=self.layout, **kwargs)

        self.state = state or SearchState()
        self._max = max_results_number or self.default_max_results_count
        self._last_response_signature: tuple | None = None
        # Pre-allocate button pool at init (one-time ~1.3s cost for 200 buttons)
        # to eliminate per-search creation cost (~2.7ms for 5 buttons).
        self.buttons: list[SearchResultButtonBox] = []
        self._button_pool_size = self.default_button_pool_size
        self._replenish_threshold = int(self._button_pool_size * self.default_button_pool_replenish_at)
        self._replenish_in_progress = False
        self._replenish_task: asyncio.Task | None = None
        # Pre-populate the button pool
        self._initialize_button_pool()
        self._last_visible_ranks_signature: tuple[int, ...] = ()
        self._last_expanded_signature: tuple[int, ...] = ()

    def _expanded_signature(self) -> tuple[int, ...]:
        return tuple(sorted(self.state.expanded_ranks))

    @staticmethod
    def _response_signature(resp: Response) -> tuple:
        endpoint = resp.req.endpoint if resp.req is not None else None
        if endpoint == Endpoint.LOOKUP:
            item = resp.data
            pos = item.get("position", {})
            return (
                endpoint,
                1,
                (
                    item.get("id"),
                    item.get("resultType"),
                    item.get("title"),
                    item.get("_detour", {}).get("label"),
                    pos.get("lat"),
                    pos.get("lng"),
                ),
            )
        items = resp.data.get("items", [])
        return (
            endpoint,
            len(items),
            tuple(
                (
                    item.get("id"),
                    item.get("resultType"),
                    item.get("title"),
                    item.get("_detour", {}).get("label"),
                    item.get("position", {}).get("lat"),
                    item.get("position", {}).get("lng"),
                )
                for item in items
            ),
        )

    def _initialize_button_pool(self) -> None:
        """Pre-allocate button pool at init time (~1.3s for 200 buttons)."""
        start_ns = perf_counter_ns()
        for _ in range(self._button_pool_size):
            self.buttons.append(SearchResultButtonBox(self.queue, self.state, on_result_click=self.on_result_click))
        elapsed_ns = perf_counter_ns() - start_ns
        self._on_pool_initialized(elapsed_ns, self._button_pool_size)

    async def _replenish_pool_async(self, chunk_size: int | None = None) -> None:
        """Asynchronously replenish button pool during idle phases.

        Called when pool approaches exhaustion. Creates new buttons in chunks
        to spread load across multiple event loop cycles.
        """
        chunk_size = chunk_size or self.default_button_pool_chunk_size
        self._replenish_in_progress = True
        try:
            # Create new chunk
            start_ns = perf_counter_ns()
            for _ in range(chunk_size):
                self.buttons.append(SearchResultButtonBox(self.queue, self.state, on_result_click=self.on_result_click))
                # Yield to event loop every 10 buttons to avoid blocking
                if _ % 10 == 0:
                    await asyncio.sleep(0)
            elapsed_ns = perf_counter_ns() - start_ns
            self._on_pool_replenished(elapsed_ns, chunk_size)
        finally:
            self._replenish_in_progress = False

    def _check_and_trigger_replenish(self) -> None:
        """Check if pool is near exhaustion and trigger async replenishment."""
        if (
            not self._replenish_in_progress
            and len(self.buttons) < self._replenish_threshold
            and (self._replenish_task is None or self._replenish_task.done())
        ):
            self._replenish_task = asyncio.create_task(self._replenish_pool_async())

    def _ensure_buttons(self, up_to_rank: int) -> None:
        """Ensure button pool covers *up_to_rank* (buttons pre-allocated, no creation here)."""
        # With pre-allocated pool, this is now just validation. Actual buttons created at init
        # and replenished asynchronously.
        target = min(up_to_rank + 1, self._max)
        if target > len(self.buttons):
            # Pool exhausted: this should rarely happen unless search returns >200 results
            # or replenishment hasn't completed yet. Fallback: create synchronously (blocking).
            grow_count = target - len(self.buttons)
            start_ns = perf_counter_ns()
            while len(self.buttons) < target:
                self.buttons.append(SearchResultButtonBox(self.queue, self.state, on_result_click=self.on_result_click))
            elapsed_ns = perf_counter_ns() - start_ns
            if grow_count > 0:
                self._on_buttons_grown(elapsed_ns, grow_count)

        # Check if pool is below threshold and trigger async replenishment
        self._check_and_trigger_replenish()

    def _render_visible_buttons(self, visible_ranks: list[int]) -> tuple[int, int, int]:
        """Render buttons for visible result ranks (fragmented for measurement)."""
        start_ns = perf_counter_ns()
        ranks_visited = 0
        ranks_mutated = 0
        for rank in visible_ranks:
            if rank < len(self.buttons):
                ranks_visited += 1
                if self.buttons[rank].render(rank):
                    ranks_mutated += 1
        elapsed_ns = perf_counter_ns() - start_ns
        ranks_noop = max(0, ranks_visited - ranks_mutated)
        self._on_buttons_rendered(elapsed_ns, len(visible_ranks), ranks_visited, ranks_mutated, ranks_noop)
        return ranks_visited, ranks_mutated, ranks_noop

    def _clear_expansion_for_intent(self, intent: SearchIntent | None) -> None:
        """Clear expansion state based on intent kind (fragmented for measurement)."""
        if intent is not None and intent.kind in self._collapse_intent_kinds:
            start_ns = perf_counter_ns()
            was_expanded = len(self.state.expanded_ranks)
            self.state.expanded_ranks.clear()
            elapsed_ns = perf_counter_ns() - start_ns
            self._on_expansion_cleared(elapsed_ns, was_expanded)

    def display(self, resp: Response, intent: SearchIntent | None = None) -> None:
        self._clear_expansion_for_intent(intent)
        expanded_after_clear = self._expanded_signature()
        expansion_changed = int(expanded_after_clear != self._last_expanded_signature)

        start_hydrate_ns = perf_counter_ns()
        response_signature = self._response_signature(resp)
        should_hydrate = (
            response_signature != self._last_response_signature
            or self.state.last_endpoint is None
            or not self.state.items_by_rank
        )
        if should_hydrate:
            self.state.hydrate(resp)
            self._last_response_signature = response_signature
        elapsed_hydrate_ns = perf_counter_ns() - start_hydrate_ns
        self._on_hydrate_checked(elapsed_hydrate_ns, should_hydrate)

        visible_ranks = self.state.ranks()
        if visible_ranks:
            self._ensure_buttons(max(visible_ranks))
            visible_signature = tuple(visible_ranks)
            render_pass_skippable = int(
                not should_hydrate
                and not expansion_changed
                and visible_signature == self._last_visible_ranks_signature
                and expanded_after_clear == self._last_expanded_signature
            )
            ranks_visited, ranks_mutated, ranks_noop = self._render_visible_buttons(visible_ranks)
            self._on_render_pass(render_pass_skippable, expansion_changed, ranks_visited, ranks_mutated, ranks_noop)
            self._last_visible_ranks_signature = visible_signature
            self._last_expanded_signature = expanded_after_clear
        else:
            self._on_render_pass(0, expansion_changed, 0, 0, 0)
            self._last_visible_ranks_signature = ()
            self._last_expanded_signature = expanded_after_clear

        try:
            new_children = tuple(self.buttons[rank] for rank in visible_ranks if rank < len(self.buttons))
        except IndexError:
            import traceback

            traceback.print_exc()
            raise

        if new_children != self._inner_box.children:
            self._inner_box.children = new_children

    def apply_style(self) -> None:
        # (SearchResultButton.__init__ already calls add_class("result-button")).
        if not SearchResultButtons._style_applied:
            # Note the leading dot in .result-button so we target the class, not a tag name.
            Idisplay(
                HTML("<style>.result-button div, .result-button button { font-size: 10px; }</style>"), display_id=True
            )
            SearchResultButtons._style_applied = True

    # ------------------------------------------------------------------
    # Instrumentation hooks — no-ops; override in MeteredSearchResultButtons
    # ------------------------------------------------------------------

    def _on_pool_initialized(self, elapsed_ns: int, pool_size: int) -> None:
        pass

    def _on_pool_replenished(self, elapsed_ns: int, chunk_size: int) -> None:
        pass

    def _on_buttons_grown(self, elapsed_ns: int, grow_count: int) -> None:
        pass

    def _on_buttons_rendered(
        self, elapsed_ns: int, ranks_rendered: int, ranks_visited: int, ranks_mutated: int, ranks_noop: int
    ) -> None:
        pass

    def _on_expansion_cleared(self, elapsed_ns: int, was_expanded: int) -> None:
        pass

    def _on_hydrate_checked(self, elapsed_ns: int, should_hydrate: bool) -> None:
        pass

    def _on_render_pass(
        self,
        render_pass_skippable: int,
        expansion_changed: int,
        ranks_visited: int,
        ranks_mutated: int,
        ranks_noop: int,
    ) -> None:
        pass

    def modify(self, resp: Response, intent: SearchIntent | None = None) -> None:
        target_rank = intent.materialization.rank
        self.state.update_item(target_rank, resp.data, resp)
        self._last_response_signature = None
        self._ensure_buttons(target_rank)
        if target_rank < len(self.buttons):
            self.buttons[target_rank]._last_item_id = None  # invalidate dirty-check
            self.buttons[target_rank].render(target_rank, force=True)
