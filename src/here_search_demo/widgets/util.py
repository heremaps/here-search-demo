###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################


from importlib.resources import files

from IPython.core.interactiveshell import InteractiveShell
from IPython.display import Markdown, display as Idisplay
from ipywidgets import HTML, Layout, Output as OutputBase


def load_css(filename: str) -> str:
    return files("here_search_demo.widgets").joinpath("css", filename).read_text(encoding="utf-8")


def style_html(filename: str) -> HTML:
    return HTML(f"<style>{load_css(filename)}</style>")


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

    Designed to be used with API.log_fn: pass ``TableLogWidget.log`` as the callback.
    URLs are formatted as Markdown links by ``API.do_log`` before reaching this widget.
    """

    default_separator = "|"

    def __init__(self, *, height: int = 160, separator: str | None = None):
        self.out = Output(height=height)
        self.lines: list[str] = []
        self.separator = separator or self.default_separator
        self.fmt = InteractiveShell.instance().display_formatter.format
        self.columns_count = 1

    def log(self, url: str, extra_columns: list | None = None) -> None:
        """Append a single pre-formatted log line to the table."""
        columns = [url]
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
