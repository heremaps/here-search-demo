###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from here_search_demo.widgets.util import TableLogWidget


class _FakeFormatter:
    def format(self, record):
        return record.getMessage().upper()


def test_table_log_widget_log_stores_preformatted_line(monkeypatch):
    class _FakeMarkdown:
        def __init__(self, text):
            self.text = text

    class _FakeShell:
        def __init__(self):
            self.display_formatter = type("Formatter", (), {"format": lambda self, obj: (obj.text, {})})()

    monkeypatch.setattr(
        "here_search_demo.widgets.util.InteractiveShell",
        type("S", (), {"instance": staticmethod(_FakeShell)}),
    )
    monkeypatch.setattr("here_search_demo.widgets.util.Markdown", _FakeMarkdown)

    widget = TableLogWidget()
    md_link = "[/discover?q=test](https://discover.search.hereapi.com/v1/discover?q=test&apiKey=KEY)"
    widget.log(md_link)

    assert widget.lines[0].strip("| ").startswith("[/discover?")


def test_table_log_widget_log_accepts_extra_columns(monkeypatch):
    class _FakeMarkdown:
        def __init__(self, text):
            self.text = text

    class _FakeShell:
        def __init__(self):
            self.display_formatter = type("Formatter", (), {"format": lambda self, obj: (obj.text, {})})()

    monkeypatch.setattr(
        "here_search_demo.widgets.util.InteractiveShell",
        type("S", (), {"instance": staticmethod(_FakeShell)}),
    )
    monkeypatch.setattr("here_search_demo.widgets.util.Markdown", _FakeMarkdown)

    widget = TableLogWidget()
    widget.log("[/browse?at=1,2](https://browse.search.hereapi.com/v1/browse?at=1,2)", extra_columns=["(cached)"])

    assert "(cached)" in widget.lines[0]
