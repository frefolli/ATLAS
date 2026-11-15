"""«Scarta»: the button before «Salva» when there are local changes, and the window showing what is lost."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEventLoop, Qt, QTimer
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


def test_closing_shows_the_local_changes_to_keep_or_discard(app, tmp_path, monkeypatch):
    p = published(tmp_path)
    saved = p.new_element("domain", name="Radio")
    p.save()  # saved, not published (e.g. a step composed in a view)
    p.new_element("domain", name="Frenatura")  # not saved
    window = window_on(p)
    shown = []
    # At once the window of the local changes (no question before it): «Salva» first.
    monkeypatch.setattr(DiscardDialog, "exec", lambda d: shown.append(d) or False)
    assert not window._confirm_discard()  # «Annulla» in the window: the project stays open
    d = shown[0]
    assert d.windowTitle() == "Modifiche locali" and d.save_button.isDefault() and d.save_button.text() == "Salva"
    assert len(d.diff.changes) == 2 and d.needs is not None  # saved or not, all of them; ticks to choose
    # «Esci senza scartare»: what is not saved is not saved, what is saved stays local.
    assert d.leave_button is not None
    monkeypatch.setattr(DiscardDialog, "exec", lambda d: d._leave_chosen() or True)
    assert window._confirm_discard(reopen=False)
    assert names(Project.open(p.path)) == ["Odometria", "Radio"]
    assert p.is_modified  # still in memory here (the window would close it)
    # «Salva»: what is not saved is saved; all of it stays local.
    monkeypatch.setattr(DiscardDialog, "exec", lambda d: d._save_chosen() or True)
    assert window._confirm_discard() and not window.project.is_modified
    assert names(Project.open(p.path)) == ["Frenatura", "Odometria", "Radio"]
    # Nothing left to save: «Esci senza scartare», the first choice (no «Salva»).
    monkeypatch.setattr(DiscardDialog, "exec", lambda d: shown.append(d) or False)
    window._confirm_discard()
    assert shown[-1].save_button is None and shown[-1].leave_button.isDefault()
    # «Scarta» with one ticked off: the others are lost, also those saved; the project opened again.
    def some(d):
        d.view.chosen.discard(saved.uuid)
        return True
    monkeypatch.setattr(DiscardDialog, "exec", some)
    assert window._confirm_discard()
    assert names(window.project) == ["Odometria", "Radio"] and window.project.has_unpublished_changes()
    # «Scarta» everything: back to the last published version, nothing local any more.
    monkeypatch.setattr(DiscardDialog, "exec", lambda d: True)
    assert window._confirm_discard()
    assert names(window.project) == ["Odometria"] and not window.project.has_unpublished_changes()
    shown.clear()
    assert window._confirm_discard() and not shown  # nothing local: no window
    window._set_project(None)
    window.close()


def test_closing_a_project_never_published_discards_what_is_not_saved(app, tmp_path, monkeypatch):
    p = Project.create(tmp_path / "p", "Prova")
    p.new_element("domain", name="Radio")
    window = window_on(p)
    shown = []
    monkeypatch.setattr(DiscardDialog, "exec", lambda d: shown.append(d) or True)
    assert window._confirm_discard(reopen=False) and shown[0].needs is None and len(shown[0].diff.changes) == 1
    window._set_project(None)
    assert names(Project.open(p.path)) == []
    window.close()


# --- discarding some of the changes only ---------------------------------------------------------------------------

def linked(tmp_path):
    """Published: Odometria. Local: Radio, a function in it (it needs Radio), Odometria renamed, Frenatura removed."""
    p = published(tmp_path)
    braking = p.new_element("domain", name="Frenatura")
    p.save()
    p.publish("v2", AUTHOR)
    old = next(d for d in p.model.of_kind("domain") if d.get("name") == "Odometria")
    radio = p.new_element("domain", name="Radio")
    session = p.new_element("system_function", name="Stabilire la sessione", domain=radio.uuid)
    old.set("name", "Odometria e localizzazione")
    p.update(old)
    p.delete_element(braking.uuid)
    p.save()
    return p, old, radio, session, braking


def ticks(view):
    items = {}
    for i in range(view.tree.topLevelItemCount()):
        group = view.tree.topLevelItem(i)
        for j in range(group.childCount()):
            items[group.child(j).data(0, 0x0100).uuid] = group.child(j)
    return items


def test_some_changes_only_are_discarded_the_others_stay_local(tmp_path):
    p, old, radio, session, braking = linked(tmp_path)
    p.discard_some({radio.uuid, session.uuid, braking.uuid})
    reopened = Project.open(p.path)
    assert names(reopened) == ["Frenatura", "Odometria e localizzazione"]  # the removal discarded: it is back
    assert reopened.model.get(session.uuid) is None
    assert reopened.changed_elements() == [old.uuid] and reopened.has_unpublished_changes()


def test_the_window_ticks_with_a_change_to_discard_those_linked_to_it(app, tmp_path):
    p, old, radio, session, braking = linked(tmp_path)
    dialog = DiscardDialog(p, selectable=True)
    view = dialog.view
    assert view.chosen == {old.uuid, radio.uuid, session.uuid, braking.uuid}
    assert dialog.chosen() is None  # everything: as before
    items = ticks(view)
    for item in items.values():
        item.setCheckState(0, Qt.Unchecked)
    assert dialog.chosen() == set() and not dialog.discard_button.isEnabled()
    items[radio.uuid].setCheckState(0, Qt.Checked)  # the domain discarded: the function in it goes too
    assert view.chosen == {radio.uuid, session.uuid} and items[session.uuid].checkState(0) == Qt.Checked
    assert "Da scartare anche, perché collegate" in view.note.text() and "Stabilire la sessione" in view.note.text()
    assert "Da scartare: 2 di 4 modifiche · 2 restano locali" in dialog.chosen_label.text()
    assert dialog.discard_button.text() == "Scarta 2 modifiche"
    items[session.uuid].setCheckState(0, Qt.Unchecked)  # the function kept: the domain it needs is kept too
    assert view.chosen == set() and "Tenute anche, perché servono" in view.note.text()
    items[session.uuid].setCheckState(0, Qt.Checked)  # only the function: the domain stays
    assert dialog.chosen() == {session.uuid}
    # Frenatura back (its removal discarded): Radio, which has its DF02 now, goes too, with its function.
    items[braking.uuid].setCheckState(0, Qt.Checked)
    assert dialog.chosen() == {braking.uuid, radio.uuid, session.uuid}
    items[radio.uuid].setCheckState(0, Qt.Unchecked)  # Radio kept: Frenatura stays removed (the function can go)
    assert dialog.chosen() == {session.uuid} and items[braking.uuid].checkState(0) == Qt.Unchecked
    # Before leaving a branch, or closing without saving: everything, without ticks.
    assert DiscardDialog(p).needs is None and DiscardDialog(p).chosen() is None


def test_discarding_from_the_window_some_changes_only(app, tmp_path, monkeypatch):
    p, old, radio, session, braking = linked(tmp_path)
    window = window_on(p)

    def choose(dialog):
        items = ticks(dialog.view)
        for item in items.values():
            item.setCheckState(0, Qt.Unchecked)
        items[radio.uuid].setCheckState(0, Qt.Checked)
        return True
    monkeypatch.setattr(DiscardDialog, "exec", choose)
    assert window.discard_local_changes()
    assert names(window.project) == ["Odometria e localizzazione"]  # Frenatura still removed, locally
    assert sorted(window.project.changed_elements()) == sorted([old.uuid, braking.uuid])
    assert "Scartate 2 modifiche locali" in window.statusBar().currentMessage()
    window._set_project(None)
    window.close()


def test_the_graphic_views_by_their_type(app, tmp_path):
    from arcadia_tool.model.schema import DIAGRAM_CHAIN, DIAGRAM_DATAFLOW
    p = published(tmp_path)
    chain = p.new_element("functional_chain", title="Accensione")
    path = p.new_element("diagram", name="Accensione", diagram_type=DIAGRAM_CHAIN, chain=chain.uuid)
    flow = p.new_element("diagram", name="Test", diagram_type=DIAGRAM_DATAFLOW)
    p.save()
    dialog = DiscardDialog(p, selectable=True)
    tree = dialog.view.tree
    views = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                 if tree.topLevelItem(i).text(0) == "Viste grafiche")
    # Under «Viste grafiche», a group for each type, as in the tree of the views.
    assert [views.child(i).text(0) for i in range(views.childCount())] == ["SA-5 Dataflow funzionali",
                                                                           "SA-7 Catene funzionali"]
    assert views.child(0).child(0).text(0) == "Test" and views.child(1).child(0).text(0) == "Accensione"
    # A tick taken off inside a group: the change stays local.
    views.child(0).child(0).setCheckState(0, Qt.Unchecked)
    assert flow.uuid not in dialog.view.chosen and path.uuid in dialog.view.chosen
    assert views.child(0).checkState(0) == Qt.Unchecked and views.checkState(0) == Qt.PartiallyChecked
