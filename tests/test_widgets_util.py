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


def test_table_log_widget_uses_url_to_md_link(monkeypatch):
    class _FakeMarkdown:
        def __init__(self, text):
            self.text = text

    class _FakeShell:
        def __init__(self):
            self.display_formatter = type("Formatter", (), {"format": lambda self, obj: (obj.text, {})})()

    # Patch IPython/Markdown dependencies out so we only exercise our logic
    monkeypatch.setattr(
        "here_search_demo.widgets.util.InteractiveShell",
        type("S", (), {"instance": staticmethod(_FakeShell)}),
    )
    monkeypatch.setattr("here_search_demo.widgets.util.Markdown", _FakeMarkdown)

    widget = TableLogWidget()

    # Spy on url_to_md_link to ensure log() delegates to it
    calls = {}

    def fake_url_to_md_link(url: str) -> str:
        calls["url"] = url
        return f"[LABEL]({url})"

    monkeypatch.setattr(
        "here_search_demo.widgets.util.TableLogWidget.url_to_md_link",
        staticmethod(fake_url_to_md_link),
    )

    url = "https://example.com/v1/discover?q=test"
    widget.log(url)

    # log() must have called url_to_md_link with the URL
    assert calls["url"] == url
    # and stored the returned Markdown link in the first line
    assert widget.lines[0].strip("| ").startswith("[LABEL](")


def test_table_log_widget_url_to_md_link_strips_apikey_from_label():
    widget = TableLogWidget()
    url = "https://example.com/v1/discover?q=test&apiKey=SECRET&lang=en"

    md = widget.url_to_md_link(url)

    # Split into label and href parts
    label, href = md.split("](")
    label = label.lstrip("[")
    href = href.rstrip(")")

    # Label should show relative path and cleaned query (no apiKey)
    assert label.startswith("/discover?")
    assert "apiKey" not in label

    # Href should contain the original full URL (with apiKey)
    assert href == url
