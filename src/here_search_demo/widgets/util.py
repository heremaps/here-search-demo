###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import urllib.parse

from IPython.core.interactiveshell import InteractiveShell
from IPython.display import Markdown, display as Idisplay
from ipyleaflet import Map
from ipywidgets import Layout, Output as OutputBase
from yarl import URL


class Output(OutputBase):
    default_height = 30
    out_stream = lambda t: {"name": "stdout", "output_type": "stream", "text": t}  # noqa: E731

    def __init__(self, **kwargs):
        height = kwargs.get("height", Output.default_height)
        super().__init__(
            layout=Layout(
                height=f"{height}px",
                border="1px solid black",
                overflow="auto",
            )
        )
        self.layout.white_space = "nowrap"

    def _format(self, **kwargs) -> dict:
        fmt = {"name": "stdout", "output_type": "stream"}
        fmt.update(kwargs)
        return fmt

    def replace(self, message: str):
        self.outputs = (self._format(text=message),)

    def add(self, message: str):
        # prepend the freshly formatted message to the existing widget outputs
        self.outputs = (self._format(text=message),) + getattr(self, "outputs", tuple())


class TableLogWidget:
    """Lightweight widget that renders log lines as a Markdown table.

    Designed to be used with API.log_fn: pass ``TableLogWidget.log``
    as the callback and ``TableLogWidget.url_to_md_link`` as url_format_fn.
    """

    default_separator = "|"

    def __init__(self, *, height: int = 160, separator: str | None = None):
        self.out = Output(height=height)
        self.lines: list[str] = []
        self.separator = separator or self.default_separator
        self.fmt = InteractiveShell.instance().display_formatter.format
        self.columns_count = 1

    @staticmethod
    def url_to_md_link(url: str) -> str:
        human_readable_url = URL(url).human_repr()
        parts = urllib.parse.urlparse(human_readable_url)
        endpoint_str = parts.path.rsplit("/", 1)[-1]
        params = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
        params.pop("apiKey", None)
        if "route" in params:
            params["route"] = ["..."]  # hide route details for better readability
        params_str = urllib.parse.unquote(
            urllib.parse.urlencode({k: ",".join(v) if isinstance(v, list) else v for k, v in params.items()})
        )
        if params_str:
            # Label shows relative path + cleaned query; href is full original URL
            return f"[/{endpoint_str}?{params_str}]({url})"
        else:
            return f"[/{endpoint_str}]({url})"

    def log(self, url: str, formatted: bool = False, extra_columns: list | None = None) -> None:
        """Append a single log line to the table.

        ``url`` is rendered as a Markdown link unless ``formatted`` is True,
        in which case it is assumed to be pre-formatted (e.g. cached).
        """
        formatted_url = self.url_to_md_link(url) if not formatted else url
        columns = [formatted_url]
        if extra_columns:
            columns.extend(extra_columns)
        formatted_record = "|".join(columns)
        self.lines.insert(0, f"| {formatted_record} |")

        self.columns_count = max(self.columns_count, len(columns))
        header = [
            f"| {'&nbsp; ' * 100} |" + "| " * (self.columns_count - 1),
            f"{'|:-' * self.columns_count}|",
        ]

        table_md = "\n".join(header + self.lines)
        log_output = Markdown(table_md)
        data, metadata = self.fmt(log_output)
        self.out.outputs = ({"output_type": "display_data", "data": data, "metadata": metadata},)

    def show(self) -> None:
        Idisplay(self.out)

    def clear_logs(self) -> None:
        self.out.clear_output()
        self.lines.clear()


class FakeRouteController:
    route = None
    flexpolyline = None
    all_along = None
    fake = True

    def __init__(self, map_instance: Map):
        pass

    def get_route_select_options(self):
        return {}

    def get_route_checkbox_options(self):
        return {}

    def get_widgets(self, *args):
        return []
