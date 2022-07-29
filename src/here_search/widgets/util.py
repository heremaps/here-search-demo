from IPython.display import display as Idisplay
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
            'border': '1px solid black'
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
