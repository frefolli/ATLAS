"""«Propaga…» (Design Authority only): the versions of the branch in use integrated into the branches chosen, one at a
time, with the window of «Integra»; back on the branch in use at the end, with a summary."""
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from arcadia_tool.storage.project import Project, Receive

AUTHOR = "Prova <prova@example.com>"
ANNA = SimpleNamespace(id="a" * 32, full_name="Anna Bianchi", email="a@x.it", username="anna")
MARIO = SimpleNamespace(id="b" * 32, full_name="Mario Rossi", email="m@x.it", username="mario")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def reopen(p):
    p.close()
    return Project.open(p.path)


def build(tmp_path):
    """master with the DA (RFI: Anna); att/T2 and att/T3 from its first version, att/T2 with a domain of its own;
    then on master a new domain: two versions of master missing in both branches."""
    p = Project.create(tmp_path / "p", "Prova")
    rfi = p.new_element("team", name="RFI", design_authority=True, members=[{"name": "Anna Bianchi",
                                                                             "account": "a" * 32}])
    p.new_element("team", name="FBK", members=[{"name": "Mario Rossi", "account": "b" * 32}])
    p.new_element("domain", name="Odometria", team=rfi.uuid)
    p.save()
    v1 = p.publish("v1", AUTHOR)
    p.switch_branch("att/T3", v1)
    p.switch_branch("att/T2", v1)
    p = reopen(p)
    p.new_element("domain", name="Radio")
    p.save()
    p.publish("radio", AUTHOR)
    p.switch_branch("master")
    p = reopen(p)
    p.new_element("domain", name="Frenatura")
    p.save()
    p.publish("frenatura", AUTHOR)
    p.new_element("domain", name="Modi")
    p.save()
    p.publish("modi", AUTHOR)
    return p


def domains_on(p, branch):
    return sorted(e.get("name") for e in p.repository.model_at(p.repository.local_heads()[branch]).of_kind("domain"))


def test_what_each_branch_lacks(tmp_path):
    p = build(tmp_path)
    assert dict(p.propagation_targets()) == {"att/T2": 2, "att/T3": 2}
    assert dict(p.propagation_targets("att/T2")) == {"master": 1, "att/T3": 1}
    p.close()


def test_the_window_of_the_branches(app, tmp_path):
    from PySide6.QtCore import Qt
    from arcadia_tool.ui.propagate import PropagateDialog

    p = build(tmp_path)
    dialog = PropagateDialog(p, {}, fetch=False)
    texts = [dialog.list.item(i).text() for i in range(dialog.list.count())]
    assert texts == ["att/T2  ·  2 versioni di «master» da integrare", "att/T3  ·  2 versioni di «master» da integrare"]
    assert dialog.chosen == ["att/T2", "att/T3"] and dialog.ok.isEnabled()
    assert not dialog.send.isEnabled() and not dialog.fetch_button.isVisibleTo(dialog)  # no repository
    dialog.list.item(1).setCheckState(Qt.Unchecked)
    assert dialog.chosen == ["att/T2"] and dialog.status.text() == "1 ramo scelto"
    dialog.list.item(0).setCheckState(Qt.Unchecked)
    assert not dialog.ok.isEnabled()
    p.close()


def test_only_the_design_authority_sees_it_and_the_branches_are_integrated_one_at_a_time(app, tmp_path, monkeypatch):
    from arcadia_tool.ui import main_window as mw
    from arcadia_tool.ui.propagate import PropagateDialog
    from arcadia_tool.ui.receive import ReceiveDialog

    p = build(tmp_path)
    window = mw.MainWindow()
    window.user = MARIO
    window._set_project(p)
    window.open_project = lambda path, confirmed=False, **_kw: window._set_project(Project.open(path))
    assert not window.propagate_action.isVisible() and window.propagate_changes() is None  # not of the DA
    window.user = ANNA
    window._refresh_state()
    assert window.propagate_action.isVisible() and window.propagate_action.isEnabled()
    toolbar = [a.text() for a in window.findChild(mw.QToolBar).actions()]
    assert toolbar.index("Propaga…") == toolbar.index("Pubblica…") + 1  # right after «Pubblica»

    integrated, summary, asked = [], [], []

    def run(d):  # the window of «Integra»: the first one cancelled, the second one applied
        integrated.append(d.project.current_branch())
        if len(integrated) == 1:
            return False
        d.start()
        d.worker.wait(20000)
        app.processEvents()
        assert d.receive.state in (Receive.MERGE, Receive.FAST_FORWARD) and d.integrate[0] == "master"
        d.apply()
        return True
    monkeypatch.setattr(PropagateDialog, "exec", lambda d: True)  # the branches ticked at first: both
    monkeypatch.setattr(ReceiveDialog, "exec", run)
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: summary.append(a[2]))
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or mw.QMessageBox.Yes)
    outcomes = window.propagate_changes()
    assert integrated == ["att/T2", "att/T3"]  # one at a time, each on its branch
    assert outcomes == [("att/T2", "non integrato (annullato)"), ("att/T3", "integrato")]
    assert "Continuare con il ramo «att/T3»?" in asked[0]
    assert window.project.current_branch() == "master"  # back where it started
    assert "• att/T2: non integrato (annullato)" in summary[-1] and "• att/T3: integrato" in summary[-1]
    p = window.project
    assert domains_on(p, "att/T3") == ["Frenatura", "Modi", "Odometria"]
    assert domains_on(p, "att/T2") == ["Odometria", "Radio"]  # cancelled: as it was
    assert dict(p.propagation_targets()) == {"att/T2": 2, "att/T3": 0}
    window._set_project(None)
    window.close()


def test_stopped_after_a_branch_not_integrated(app, tmp_path, monkeypatch):
    from arcadia_tool.ui import main_window as mw
    from arcadia_tool.ui.propagate import PropagateDialog
    from arcadia_tool.ui.receive import ReceiveDialog

    p = build(tmp_path)
    window = mw.MainWindow()
    window.user = ANNA
    window._set_project(p)
    window.open_project = lambda path, confirmed=False, **_kw: window._set_project(Project.open(path))
    monkeypatch.setattr(PropagateDialog, "exec", lambda d: True)
    monkeypatch.setattr(ReceiveDialog, "exec", lambda d: False)
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.No)  # not to go on
    outcomes = window.propagate_changes()
    assert outcomes == [("att/T2", "non integrato (annullato)"),
                        ("att/T3", "non integrato: propagazione interrotta")]
    assert window.project.current_branch() == "master"
    window._set_project(None)
    window.close()
