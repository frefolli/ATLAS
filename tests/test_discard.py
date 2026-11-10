"""«Scarta»: the button before «Salva» when there are local changes, and the window showing what is lost."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from arcadia_tool.storage.project import Project
from arcadia_tool.ui import main_window as mw
from arcadia_tool.ui.versions import DiscardDialog

AUTHOR = "Prova <prova@example.com>"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def published(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    p.new_element("domain", name="Odometria")
    p.save()
    p.publish("v1", AUTHOR)
    return p


def names(project):
    return sorted(d.get("name") for d in project.model.of_kind("domain"))


def window_on(p):
    window = mw.MainWindow()
    window._set_project(p)
    window.open_project = lambda path, confirmed=False, **_kw: window._set_project(Project.open(path))
    return window


def settle(window):
    """The check of the changes saved and not published, as the event loop runs it."""
    window._local_timer.stop()
    window._check_local_changes()
    window._local_check.wait(20000)
    loop = QEventLoop()
    QTimer.singleShot(50, loop.quit)
    loop.exec()


def test_the_window_shows_what_is_lost(app, tmp_path):
    p = published(tmp_path)
    added = p.new_element("domain", name="Radio")
    p.save()
    dialog = DiscardDialog(p)  # also what is saved and not published
    assert [c.element.uuid for c in dialog.diff.changes] == [added.uuid]
    unsaved = p.new_element("domain", name="Frenatura")
    dialog = DiscardDialog(p, unsaved=True)  # only what is not saved
    assert [c.element.uuid for c in dialog.diff.changes] == [unsaved.uuid]
    dialog.discard_button.click()
    assert dialog.result() == DiscardDialog.Accepted


def test_the_button_appears_only_with_local_changes(app, tmp_path):
    p = published(tmp_path)
    window = window_on(p)
    actions = window.findChild(mw.QToolBar).actions()
    assert actions.index(window.discard_action) == actions.index(window.save_action) - 1  # before «Salva»
    settle(window)
    assert not window.discard_action.isVisible()
    p.new_element("domain", name="Radio")
    window._model_changed()
    assert window.discard_action.isVisible()  # not saved: at once
    window.save()
    settle(window)
    assert window.discard_action.isVisible()  # saved and not published
    p.publish("v2", AUTHOR)
    window._refresh_state()
    settle(window)
    assert not window.discard_action.isVisible()
    window._set_project(None)
    assert not window.discard_action.isVisible()
    window.close()


def test_never_published_nothing_to_go_back_to(app, tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    p.new_element("domain", name="Radio")
    window = window_on(p)
    assert not window.discard_action.isVisible()
    window._set_project(None)
    window.close()


def test_discarding_asks_with_the_window_and_can_be_cancelled(app, tmp_path, monkeypatch):
    p = published(tmp_path)
    p.new_element("domain", name="Radio")
    p.save()
    window = window_on(p)
    shown = []
    monkeypatch.setattr(DiscardDialog, "exec", lambda d: shown.append(d.diff) or False)  # «Annulla»
    window.discard_action.trigger()
    assert shown and shown[0] and names(window.project) == ["Odometria", "Radio"]
    monkeypatch.setattr(DiscardDialog, "exec", lambda d: True)  # «Scarta le modifiche»
    window.discard_action.trigger()
    assert names(window.project) == ["Odometria"]
    assert not window.project.has_unpublished_changes() and not window.project.is_modified
    window._set_project(None)
    window.close()


def test_closing_without_saving_shows_what_is_lost(app, tmp_path, monkeypatch):
    p = published(tmp_path)
    p.new_element("domain", name="Radio")
    window = window_on(p)
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: QMessageBox.Discard)
    shown = []
    monkeypatch.setattr(DiscardDialog, "exec", lambda d: shown.append(d.diff) or False)
    assert not window._confirm_discard()  # «Annulla» in the window: the project stays open
    assert shown[0]
    monkeypatch.setattr(DiscardDialog, "exec", lambda d: True)
    assert window._confirm_discard()
    window._set_project(None)
    window.close()
