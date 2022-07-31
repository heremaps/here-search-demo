from IPython.display import display as Idisplay, Markdown
from IPython.core.interactiveshell import InteractiveShell
from ipywidgets import Output

import logging


class LogWidgetHandler(logging.Handler):
    """
    Custom logging handler sending logs to an output widget
    Ref: https://ipywidgets.readthedocs.io/en/stable/examples/Output%20Widget.html#Integrating-output-widgets-with-the-logging-module
    """

    def __init__(self, *args, **kwargs):
        super(LogWidgetHandler, self).__init__(*args, **kwargs)
        layout = {
            'width': '100%',
            'height': '160px',
            'border': '1px solid black',
            'overflow': 'auto',
            'white-space': 'nowrap'
        }
        self.out = Output(layout=layout)

    def emit(self, record):
        """ Overload of logging.Handler method """
        formatted_record = self.format(record)
        new_output = {
            'name': 'stdout',
            'output_type': 'stream',
            'text': formatted_record+'\n'
        }
        self.out.outputs = (new_output, ) + self.out.outputs

    def show_logs(self):
        """ Show the logs """
        Idisplay(self.out)

    def clear_logs(self):
        """ Clear the current logs """
        self.out.clear_output()


class TableLogWidgetHandler(LogWidgetHandler):
    default_separator = "|"

    def __init__(self, *args, **kwargs):
        super(TableLogWidgetHandler, self).__init__(*args, **kwargs)
        self.lines = []
        self.separator = kwargs.pop("separator", TableLogWidgetHandler.default_separator)
        self.fmt = InteractiveShell.instance().display_formatter.format
        self.columns_count = 1

    def emit(self, record):
        """ Overload of logging.Handler method """
        formatted_record = self.format(record)
        self.lines.insert(0, f"| {formatted_record} |")

        self.columns_count = max(self.columns_count, len(formatted_record.split(self.separator)))
        header = ['| <div style="width:70%"></div> |' + '| '*(self.columns_count-1), f"{'|:-'*self.columns_count}|"]

        log_output = Markdown("\n".join(header + self.lines))
        fmt = InteractiveShell.instance().display_formatter.format
        data, metadata = fmt(log_output)
        self.out.outputs = {'output_type': 'display_data', 'data': data, 'metadata': metadata},