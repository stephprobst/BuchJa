"""Unit tests for the StatusFooter component.

These tests avoid rendering NiceGUI UI by faking the small surface area of
nicegui.ui used by StatusFooter.
"""

import pytest


class _FakeContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def classes(self, *_args, **_kwargs):
        return self


class _FakeFooter(_FakeContext):
    def __init__(self):
        self.visible = True
        self.visibility_calls: list[bool] = []

    def set_visibility(self, visible: bool):
        self.visible = visible
        self.visibility_calls.append(visible)


class _FakeRow(_FakeContext):
    pass


class _FakeLabel:
    def __init__(self, text: str):
        self.text = text

    def classes(self, *_args, **_kwargs):
        return self


class _FakeSpinner:
    def __init__(self, *_args, **_kwargs):
        pass

    def classes(self, *_args, **_kwargs):
        return self


class _FakeUI:
    def __init__(self):
        self.footer_el = _FakeFooter()
        self.label_el = _FakeLabel("")

    def footer(self):
        return self.footer_el

    def row(self):
        return _FakeRow()

    def label(self, text: str):
        self.label_el = _FakeLabel(text)
        return self.label_el

    def spinner(self, *args, **kwargs):
        return _FakeSpinner(*args, **kwargs)


@pytest.mark.unit
def test_status_footer_hidden_by_default(monkeypatch):
    from src.components import status_footer as mod

    fake_ui = _FakeUI()
    monkeypatch.setattr(mod, "ui", fake_ui)

    footer = mod.StatusFooter()
    assert footer._footer.visible is False
    assert footer._footer.visibility_calls[-1] is False


@pytest.mark.unit
def test_status_footer_start_and_end(monkeypatch):
    from src.components import status_footer as mod

    fake_ui = _FakeUI()
    monkeypatch.setattr(mod, "ui", fake_ui)

    footer = mod.StatusFooter()

    token = footer.start("Working...")
    assert footer._footer.visible is True
    assert footer._label.text == "Working..."

    footer.end(token)
    assert footer._footer.visible is False


@pytest.mark.unit
def test_status_footer_stack_behavior(monkeypatch):
    from src.components import status_footer as mod

    fake_ui = _FakeUI()
    monkeypatch.setattr(mod, "ui", fake_ui)

    footer = mod.StatusFooter()

    token_a = footer.start("Task A")
    assert footer._label.text == "Task A"

    token_b = footer.start("Task B")
    assert footer._label.text == "Task B"

    footer.end(token_b)
    assert footer._footer.visible is True
    assert footer._label.text == "Task A"

    footer.end(token_a)
    assert footer._footer.visible is False
