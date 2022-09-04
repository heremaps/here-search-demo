from IPython.display import display as Idisplay, Markdown
from IPython.core.interactiveshell import InteractiveShell
from ipywidgets import Output as OutputBase

import logging


class Output(OutputBase):
    default_height = 30
    out_stream = lambda t: {'name': 'stdout', 'output_type': 'stream', 'text': t}

    def __init__(self, **kwargs):
        height = kwargs.get("height", Output.default_height)
        super().__init__(layout={'height': f'{height}px', 'border': '1px solid black', 'overflow': 'auto', 'white-space': 'nowrap'})

    def _format(self, **kwargs) -> dict:
        fmt = {'name': 'stdout', 'output_type': 'stream'}
        fmt.update(kwargs)
        return fmt

    def replace(self, message: str):
        self.outputs = (self._format(text=message), )

    def add(self, message: str):
        self.outputs = (self._format(text=message), ) + self.out.outputs


class TableLogHandler(OutputBase):
    """
    Custom logging handler sending logs to an output widget
    Ref: https://ipywidgets.readthedocs.io/en/stable/examples/Output%20Widget.html#Integrating-output-widgets-with-the-logging-module
    """
    default_separator = "|"
    default_height = 160

    def __init__(self, *args, **kwargs):
        height = kwargs.get("height", TableLogHandler.default_height)
        self.handler = logging.Handler(*args, **kwargs)
        self.lines = []
        self.separator = kwargs.pop("separator", TableLogHandler.default_separator)
        self.columns_count = 1
        super().__init__(layout={'height': f'{height}px', 'border': '1px solid black', 'overflow': 'auto', 'white-space': 'nowrap'})
        self.handler.emit = self.emit

    def emit(self, record):
        formatted_record = self.handler.format(record)
        self.lines.insert(0, f"| {formatted_record} |")

        self.columns_count = max(self.columns_count, len(formatted_record.split(self.separator)))
        header = [f'| {"&nbsp; "*100} |' + '| '*(self.columns_count-1), f"{'|:-'*self.columns_count}|"]

        log_output = Markdown("\n".join(header + self.lines))
        data, metadata = self.fmt(log_output)
        self.outputs = {'output_type': 'display_data', 'data': data, 'metadata': metadata},


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

    def emit(self, record):
        """
        Log the specified logging record.
        """
        formatted_record = self.format(record)
        self.lines.insert(0, f"| {formatted_record} |")

        self.columns_count = max(self.columns_count, len(formatted_record.split(self.separator)))
        header = [f'| {"&nbsp; "*100} |' + '| '*(self.columns_count-1), f"{'|:-'*self.columns_count}|"]

        log_output = Markdown("\n".join(header + self.lines))
        fmt = InteractiveShell.instance().display_formatter.format
        data, metadata = fmt(log_output)
        self.out.outputs = {'output_type': 'display_data', 'data': data, 'metadata': metadata},

    def clear_logs(self):
        """ Clear the current logs """
        self.out.clear_output()
