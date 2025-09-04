###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import logging
import urllib.parse

from IPython.core.interactiveshell import InteractiveShell
from IPython.display import Markdown
from IPython.display import display as Idisplay
from ipywidgets import Output as OutputBase


class Output(OutputBase):
    default_height = 30
    out_stream = lambda t: {"name": "stdout", "output_type": "stream", "text": t}  # noqa: E731

    def __init__(self, **kwargs):
        height = kwargs.get("height", Output.default_height)
        super().__init__(
            layout={
                "height": f"{height}px",
                "border": "1px solid black",
                "overflow": "auto",
                "white-space": "nowrap",
            }
        )

    def _format(self, **kwargs) -> dict:
        fmt = {"name": "stdout", "output_type": "stream"}
        fmt.update(kwargs)
        return fmt

    def replace(self, message: str):
        self.outputs = (self._format(text=message),)

    def add(self, message: str):
        self.outputs = (self._format(text=message),) + self.out.outputs


class LogWidgetHandler(logging.Handler):
    """
    Custom logging handler sending logs to an output widget
    Ref: https://ipywidgets.readthedocs.io/en/stable/examples/Output%20Widget.html#Integrating-output-widgets-with-the-logging-module
    """

    def __init__(self, *args, **kwargs):
        super(LogWidgetHandler, self).__init__(*args, **kwargs)
        self.out = Output(height=160)

    def emit(self, record: logging.LogRecord):
        """Do the actual logging"""
        formatted_record = self.format(record)
        self.out.add(formatted_record)

    def show_logs(self):
        """Show the logs"""
        Idisplay(self.out)

    def clear_logs(self):
        """Clear the current logs"""
        self.out.clear_output()


class TableLogWidgetHandler(logging.Handler):
    """
    Custom logging handler sending logs to an output widget
    Ref: https://ipywidgets.readthedocs.io/en/stable/examples/Output%20Widget.html#Integrating-output-widgets-with-the-logging-module
    """

    default_separator = "|"

    def __init__(self, *args, **kwargs):
        super(TableLogWidgetHandler, self).__init__(*args, **kwargs)
        self.out = Output(height=160)
        self.lines = []
        self.separator = kwargs.pop("separator", TableLogWidgetHandler.default_separator)
        self.fmt = InteractiveShell.instance().display_formatter.format
        self.columns_count = 1

    @staticmethod
    def format_url(url: str) -> str:
        parts = urllib.parse.urlparse(url)
        endpoint_str = parts.path.split("/")[-1]
        params = {k: (",".join(v) if isinstance(v, list) else v) for k, v in urllib.parse.parse_qs(parts.query).items()}
        params.pop("apiKey", None)
        params_str = urllib.parse.unquote(urllib.parse.urlencode(params))
        return f"[/{endpoint_str}?{params_str}]({url})"

    def emit(self, record: logging.LogRecord):
        """
        Log the specified logging record.
        """
        record.msg = "|".join(record.getMessage().split())
        formatted_record = self.format(record)
        self.lines.insert(0, f"| {formatted_record} |")

        self.columns_count = max(self.columns_count, len(formatted_record.split(self.separator)))
        header = [
            f"| {'&nbsp; ' * 100} |" + "| " * (self.columns_count - 1),
            f"{'|:-' * self.columns_count}|",
        ]

        log_output = Markdown("\n".join(header + self.lines))
        fmt = InteractiveShell.instance().display_formatter.format
        data, metadata = fmt(log_output)
        self.out.outputs = ({"output_type": "display_data", "data": data, "metadata": metadata},)

    def clear_logs(self):
        """Clear the current logs"""
        self.out.clear_output()
