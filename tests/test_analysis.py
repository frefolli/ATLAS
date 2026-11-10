"""«Analizzato» on the clauses of the SRS catalogue: who has taken a clause in charge, saved in the model."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QHelpEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QToolTip

from arcadia_tool.accounts import Account
from arcadia_tool.model import analysis as a
from arcadia_tool.storage.project import Project
from arcadia_tool.ui.theme import apply_theme

MARIO, LUCA, ANNA = "a" * 32, "b" * 32, "c" * 32


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


def account(ident, first, last):
    return Account(id=ident, first_name=first, last_name=last, username=first.lower(), email=f"{first}@x.it")


def build(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    t1 = p.new_element("team", name="RFI", members=[{"name": "Mario Rossi", "account": MARIO},
                                                      {"name": "Luca Verdi", "account": LUCA}])
    t2 = p.new_element("team", name="FBK", members=[{"name": "Anna Bianchi", "account": ANNA}])
    chapter = p.new_element("requirement", id="3.14", item_type="Capitolo", title="Brake")
    section = p.new_element("requirement", id="3.14.4", item_type="Sezione", parent=chapter.uuid, title="Standstill")
    clause = p.new_element("requirement", id="3.14.4.2", item_type="Requisito", parent=section.uuid,
                           category=["Bordo"], text="When a movement is detected")
    p.save()
    p.publish("v1", "Prova <prova@example.com>")
    return p, clause, t1, t2


def test_each_person_marks_and_takes_back_their_own(tmp_path):
    p, clause, t1, t2 = build(tmp_path)
    mario, luca, anna = account(MARIO, "Mario", "Rossi"), account(LUCA, "Luca", "Verdi"), account(ANNA, "Anna", "Bianchi")
    assert a.mark_denied(p.model, account("d" * 32, "Ospite", "Esterno"))  # not in a team: may not
    assert a.mark_denied(p.model, mario) is None
    changed, marked = a.toggle(p, clause, mario)
    assert marked and len(a.marks_of(p.model, clause)) == 1
    mark = a.marks_of(p.model, clause)[0]
    assert mark.get("member") == "Mario Rossi" and mark.get("team") == t1.uuid and mark.get("marked_at")
    p.save(only=changed)
    p = Project.open(p.path)  # saved in the model
    clause = p.model.get(clause.uuid)
    assert [m.get("member") for m in a.marks_of(p.model, clause)] == ["Mario Rossi"]
    a.toggle(p, clause, luca)  # another member of the same team: one more
    a.toggle(p, clause, anna)  # a member of another team: one more
    assert [m.get("member") for m in a.marks_of(p.model, clause)] == ["Mario Rossi", "Luca Verdi", "Anna Bianchi"]
    text = a.who_text(p.model, a.marks_of(p.model, clause))
    assert "Anna Bianchi (T2 FBK)" in text and "Mario Rossi (T1 RFI)" in text
    _changed, marked = a.toggle(p, clause, mario)  # Mario again: his mark taken back, the others stay
    assert not marked and [m.get("member") for m in a.marks_of(p.model, clause)] == ["Luca Verdi", "Anna Bianchi"]
    p.delete_element(clause.uuid)  # the clause removed: who analysed it goes with it
    assert not p.model.of_kind("analysis")


def _click(view, point):
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        event = QMouseEvent(kind, QPointF(point), QPointF(view.viewport().mapToGlobal(point)), Qt.LeftButton,
                            Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(view.viewport(), event)


def test_the_button_of_the_clause_row(app, tmp_path):
    from arcadia_tool.ui.main_window import MainWindow

    p, clause, t1, t2 = build(tmp_path)
    window = MainWindow()
    window.resize(1400, 900)
    window.show()
    window.user = account(MARIO, "Mario", "Rossi")
    window._set_project(p)
    window.open_srs_reader()
    reader = window.reader
    app.processEvents()
    index = reader.model.index(next(i for i, e in enumerate(reader.model.elements) if e.uuid == clause.uuid))

    def button():
        *_, actions, _ = reader.delegate._layout(clause, reader.view.visualRect(index))
        return next((label, box) for name, label, box in actions[1] if name == "analyzed")

    label, box = button()
    assert label == "Non analizzato" and reader._analysis(clause)[1] == "none"
    names = [name for name, _l, _b in reader.delegate._layout(clause, reader.view.visualRect(index))[-2][1]]
    assert names.index("analyzed") == names.index("exclude") + 1  # right of «Escludi»
    _click(reader.view, box.center())
    assert button()[0] == "Analizzato" and reader._analysis(clause)[1] == "mine"
    assert not p.is_modified and p.has_unpublished_changes()  # saved at once, to publish
    window.user = account(ANNA, "Anna", "Bianchi")  # another person, of another team
    assert reader._analysis(clause)[1] == "others"
    _click(reader.view, button()[1].center())
    label, box = button()
    assert label == "Analizzato (2)"
    tip = reader._analysis(clause)[2]
    assert "2 persone" in tip and "Mario Rossi (T1 RFI)" in tip and "Anna Bianchi (T2 FBK)" in tip
    shown = []
    original = QToolTip.showText
    QToolTip.showText = staticmethod(lambda pos, text, *rest: shown.append(text))
    try:  # the mouse on the button, without clicking
        event = QHelpEvent(QEvent.ToolTip, box.center(), reader.view.viewport().mapToGlobal(box.center()))
        reader.delegate.helpEvent(event, reader.view, None, index)
    finally:
        QToolTip.showText = original
    assert shown and "Mario Rossi" in shown[0] and "Anna Bianchi" in shown[0]
    window.user = account(MARIO, "Mario", "Rossi")
    _click(reader.view, button()[1].center())  # Mario again: his own mark taken back
    assert button()[0] == "Analizzato" and reader._analysis(clause)[1] == "others"
    assert not reader.grab().isNull()
    window._set_project(None)
    window.close()
    window.deleteLater()
    app.processEvents()
    assert QPoint  # imported for the events above
