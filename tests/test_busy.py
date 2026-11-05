"""Saving and publishing in a thread, with a window saying so only when they take time."""
import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from arcadia_tool.storage.project import Project
from arcadia_tool.ui import busy
from arcadia_tool.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def shown(monkeypatch):
    """What the windows of the operations said, and whether they were closed."""
    windows = []

    class Recording(busy.QProgressDialog):
        def __init__(self, text, *args):
            super().__init__(text, *args)
            windows.append(self)
            self.texts = [text]

        def setLabelText(self, text):
            self.texts.append(text)
            super().setLabelText(text)
    monkeypatch.setattr(busy, "QProgressDialog", Recording)
    return windows


def test_a_quick_operation_shows_nothing(app, shown):
    parent = QWidget()
    assert busy.run_busy(parent, "Salvataggio in corso…", lambda report: threading.current_thread().name) != \
        threading.current_thread().name  # in its own thread
    assert not shown


def test_a_long_operation_says_so_and_gets_its_reports(app, shown, monkeypatch):
    monkeypatch.setattr(busy, "SHOW_AFTER_MS", 10)
    parent = QWidget()

    def work(report):
        time.sleep(0.2)
        report("Salvataggio in corso… 50 di 100 schede")
        time.sleep(0.2)
        return 7

    assert busy.run_busy(parent, "Salvataggio in corso…", work) == 7
    assert len(shown) == 1 and shown[0].texts == ["Salvataggio in corso…", "Salvataggio in corso… 50 di 100 schede"]
    assert not shown[0].isVisible()  # closed at the end


def test_the_error_of_the_operation_reaches_the_caller(app, shown):
    def work(report):
        raise ValueError("disco pieno")

    with pytest.raises(ValueError, match="disco pieno"):
        busy.run_busy(QWidget(), "Salvataggio in corso…", work)


def test_the_saves_of_the_window_go_through_the_indicator(app, shown, monkeypatch, tmp_path):
    monkeypatch.setattr(busy, "SHOW_AFTER_MS", 0)
    p = Project.create(tmp_path / "p", "Prova")
    domain = p.new_element("domain", name="Odometria")
    original = Project._save

    def slow(self, *args):  # a project of thousands of sheets
        time.sleep(0.2)
        original(self, *args)
    monkeypatch.setattr(Project, "_save", slow)
    window = MainWindow()
    window._set_project(p)
    window.save()
    assert shown and shown[0].texts[0] == "Salvataggio in corso…"
    assert not p.is_modified and (tmp_path / "p").joinpath(p._relative(p.element_file(domain))).is_file()
    window._set_project(None)
    window.close()
