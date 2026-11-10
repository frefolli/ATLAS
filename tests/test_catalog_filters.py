"""The filters of the catalogues: the SRS clauses of all, of some teams or of some functional domains; the ADR by
conditions on their columns, in AND and OR, with brackets."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QComboBox

from arcadia_tool.model.adr import item_domains
from arcadia_tool.model.filters import (AND, CONTAINS, EMPTY, EQUALS, NOT_CONTAINS, NOT_EMPTY, NOT_EQUALS, OR,
                                        Condition, FilterError, check, evaluate, holds)
from arcadia_tool.storage.project import Project


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# --- the expressions ----------------------------------------------------------------------------------------------

def test_the_operators():
    c = lambda op, value="": Condition("x", op, value)  # noqa: E731
    assert holds(c(CONTAINS, "radio"), "Gestione Radio") and holds(c(NOT_CONTAINS, "odo"), "Radio")
    assert holds(c(EQUALS, "df02"), "DF01, DF02") and not holds(c(EQUALS, "DF0"), "DF01, DF02")  # one of a list
    assert holds(c(NOT_EQUALS, "Proposta"), "Decisa") and not holds(c(NOT_EQUALS, "decisa"), "Decisa")
    assert holds(c(EMPTY), "  ") and holds(c(NOT_EMPTY), "x") and not holds(c(EMPTY), "x")


def test_and_binds_before_or_and_brackets_change_it():
    row = {"a": "1", "b": "0", "c": "1"}
    cell = row.get

    def cond(column, join=AND, opens=0, closes=0):
        return Condition(column, EQUALS, "1", join, opens, closes)
    assert evaluate([], cell)
    assert not evaluate([cond("a"), cond("b")], cell)  # 1 E 0
    assert evaluate([cond("a"), cond("b", OR)], cell)  # 1 O 0
    # A E B O C = (A E B) O C = 0 O 1 = 1; B E (A O C)... with brackets: B E (A O C) = 0
    assert evaluate([cond("a"), cond("b"), cond("c", OR)], cell)
    assert evaluate([cond("b"), cond("a", OR), cond("c")], cell)  # 0 O (1 E 1)
    assert not evaluate([cond("b"), cond("a", AND, opens=1), cond("c", OR, closes=1)], cell)  # 0 E (1 O 1)
    assert evaluate([cond("a", opens=2), cond("b", OR, closes=1), cond("c", AND, closes=1)], cell)  # ((1 O 0) E 1)
    assert check([cond("a", opens=1)]) and check([cond("a", closes=1), cond("b", opens=1)])
    with pytest.raises(FilterError):
        evaluate([cond("a", opens=1)], cell)


# --- the catalogue of the ADR ---------------------------------------------------------------------------------

def test_the_conditions_under_the_search_of_the_adr(app, tmp_path):
    from arcadia_tool.ui.element_list import ElementListPage

    p = Project.create(tmp_path / "p", "Prova")
    rfi, fbk = p.new_element("team", name="RFI"), p.new_element("team", name="FBK")
    p.new_element("adr", title="Radio", adr_type="Riallocazione di sezione o clausola", status="Proposta",
                  proposer=rfi.uuid)
    p.new_element("adr", title="Odometria", adr_type="Esclusione di sezione o clausola", status="Decisa",
                  proposer=fbk.uuid)
    p.new_element("adr", title="Freni", adr_type="Riallocazione di sezione o clausola", status="Decisa",
                  proposer=fbk.uuid)
    page = ElementListPage(p, "adr")
    page.show()
    layout = page.layout().itemAt(0).widget().layout()  # the header: title, search, then the conditions
    widgets = [layout.itemAt(i).widget() or layout.itemAt(i).layout() for i in range(layout.count())]
    assert widgets.index(page.filters) == 2

    def shown():
        return sorted(page.table.item(r, 1).text() for r in range(page.table.rowCount())
                      if not page.table.isRowHidden(r))
    assert shown() == ["Freni", "Odometria", "Radio"]
    first = page.filters.add()
    # Four choices: column, operator, value, and AND / OR with the next one (empty on the last).
    combos = [w for w in first.findChildren(QComboBox) if w.parent() is first]
    assert combos == [first.column, first.operator, first.value, first.connector]
    assert [first.connector.itemText(i) for i in range(first.connector.count())] == ["", "AND", "OR"]
    assert [first.column.itemText(i) for i in range(first.column.count())] == [
        "ID", "Titolo", "Tipo", "DF impattati", "Team proponente", "Membro proponente", "Stato", "Decisione DA"]
    first.column.setCurrentIndex(first.column.findData("status"))
    assert [first.value.itemText(i) for i in range(first.value.count())] == ["Decisa", "Proposta"]
    first.operator.setCurrentText(EQUALS)
    first.value.setEditText("Decisa")
    assert shown() == ["Freni", "Odometria"] and page.count.text() == "2 di 3"
    first.connector.setCurrentIndex(first.connector.findData(AND))  # a new row to fill
    assert len(page.filters.rows) == 2
    second = page.filters.rows[1]
    second.column.setCurrentIndex(second.column.findData("adr_type"))
    second.value.setEditText("Riallocazione")
    assert shown() == ["Freni"]  # Decisa AND Riallocazione
    first.connector.setCurrentIndex(first.connector.findData(OR))  # not the last row: no new one
    assert len(page.filters.rows) == 2
    assert shown() == ["Freni", "Odometria", "Radio"]  # Decisa OR Riallocazione
    third = page.filters.add("proposer", value="RFI")  # «Aggiungi condizione»: joined with AND
    assert second.connector.currentData() == AND
    assert shown() == ["Freni", "Odometria", "Radio"]  # Decisa OR (Riallocazione AND RFI)
    second.connector.setCurrentIndex(0)  # nothing between two conditions: said, and not applied
    assert "Manca AND oppure OR dopo la condizione 2" in page.filters.status.text() and len(shown()) == 3
    second.connector.setCurrentIndex(second.connector.findData(OR))
    first.connector.setCurrentIndex(first.connector.findData(AND))
    assert shown() == ["Freni", "Radio"]  # (Decisa AND Riallocazione) OR RFI
    page.filters._remove(third)
    assert shown() == ["Freni"]  # the OR of the row left last: nothing after it
    page.search.setText("freni")  # with the search too
    assert shown() == ["Freni"]
    page.search.clear()
    page.filters.clear()
    assert shown() == ["Freni", "Odometria", "Radio"] and not page.filters.rows
    page.close()  # not left open on the screen for the next tests (e.g. those with the mouse)
    page.deleteLater()
    p.close()


# --- the SRS clauses ------------------------------------------------------------------------------------------

def build_srs(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    rfi = p.new_element("team", name="RFI")
    fbk = p.new_element("team", name="FBK", members=[{"name": "Mario Rossi", "account": "b" * 32}])
    radio = p.new_element("domain", name="Radio", team=rfi.uuid)
    odo = p.new_element("domain", name="Odometria", team=fbk.uuid)
    freni = p.new_element("domain", name="Freni", team=fbk.uuid)
    chapter = p.new_element("requirement", id="3.5", item_type="Capitolo", title="Radio")
    s1 = p.new_element("requirement", id="3.5.1", item_type="Sezione", parent=chapter.uuid, primary_domain=radio.uuid,
                       contributing_domains=[odo.uuid])
    c1 = p.new_element("requirement", id="3.5.1.1", item_type="Requisito", parent=s1.uuid, text="Prima", sequence=1)
    c2 = p.new_element("requirement", id="3.5.1.2", item_type="Requisito", parent=s1.uuid, text="Seconda",
                       sequence=2, excluded_domains=[odo.uuid])
    s2 = p.new_element("requirement", id="3.5.2", item_type="Sezione", parent=chapter.uuid, primary_domain=freni.uuid)
    c3 = p.new_element("requirement", id="3.5.2.1", item_type="Requisito", parent=s2.uuid, text="Terza")
    c4 = p.new_element("requirement", id="3.5.2.2", item_type="Requisito", parent=s2.uuid, text="Quarta",
                       primary_domain=radio.uuid)  # passed to Radio by a reallocation
    return p, dict(rfi=rfi, fbk=fbk, radio=radio, odo=odo, freni=freni, c1=c1, c2=c2, c3=c3, c4=c4)


def test_the_domains_of_an_item(tmp_path):
    p, e = build_srs(tmp_path)
    assert item_domains(p.model, e["c1"]) == {e["radio"].uuid, e["odo"].uuid}
    assert item_domains(p.model, e["c2"]) == {e["radio"].uuid}  # excluded from Odometria
    assert item_domains(p.model, e["c3"]) == {e["freni"].uuid}
    assert item_domains(p.model, e["c4"]) == {e["radio"].uuid}
    p.close()


def test_the_clauses_of_teams_or_of_domains(app, tmp_path):
    from types import SimpleNamespace
    from arcadia_tool.ui.srs_reader import BY_DOMAINS, BY_TEAMS, MY_TEAM, SrsReader

    p, e = build_srs(tmp_path)
    user = [SimpleNamespace(id="b" * 32, full_name="Mario Rossi")]  # of FBK
    reader = SrsReader(p, user_of=lambda: user[0])
    reader.resize(1000, 600)
    reader.show()
    app.processEvents()

    def clauses():
        return [x.get("id") for x in reader.model.elements if x.get("item_type") == "Requisito"]
    assert clauses() == ["3.5.1.1", "3.5.1.2", "3.5.2.1", "3.5.2.2"] and not reader.scope_pick.isVisible()
    assert [reader.scope.itemText(i) for i in range(reader.scope.count())] == [
        "Tutti i requisiti", "Requisiti del mio team", "Dei team…", "Dei domini funzionali…"]
    # Under the checkboxes of the categories: a row of its own.
    header = reader.layout().itemAt(0).widget().layout()
    rows = [header.itemAt(i).layout() for i in range(header.count())]
    categories = next(i for i, r in enumerate(rows) if r is not None and r.indexOf(reader.show_headings) >= 0)
    assert rows[categories + 1].indexOf(reader.scope) >= 0
    reader.scope.setCurrentIndex(reader.scope.findData(MY_TEAM))  # Mario: FBK, Odometria and Freni
    assert clauses() == ["3.5.1.1", "3.5.2.1"] and not reader.scope_pick.isVisible()
    assert reader.scope_note.text() == "i domini di T2 FBK"
    user[0] = SimpleNamespace(id="c" * 32, full_name="Anna Bianchi")  # in no team
    reader.scope.setCurrentIndex(0)
    reader.scope.setCurrentIndex(reader.scope.findData(MY_TEAM))
    assert clauses() == [] and "non sei membro di nessun team" in reader.scope_note.text()
    reader.scope.setCurrentIndex(reader.scope.findData(BY_DOMAINS))
    assert reader.scope_pick.isVisible() and clauses() == []  # nothing chosen yet
    assert reader.scope_pick.text() == "Scegli i domini…"
    reader.scope_pick.set_values([e["odo"].uuid])
    assert clauses() == ["3.5.1.1"] and reader.scope_pick.text() == "DF02 Odometria"
    assert [x.get("id") for x in reader.model.elements][:2] == ["3.5", "3.5.1"]  # with its headings
    reader.scope_pick.set_values([e["odo"].uuid, e["freni"].uuid])
    assert clauses() == ["3.5.1.1", "3.5.2.1"] and reader.scope_pick.text() == "DF02 Odometria e altri 1"
    reader.scope.setCurrentIndex(reader.scope.findData(BY_TEAMS))
    assert clauses() == []
    reader.scope_pick.set_values([e["rfi"].uuid])  # Radio
    assert clauses() == ["3.5.1.1", "3.5.1.2", "3.5.2.2"]
    reader.scope_pick.set_values([e["fbk"].uuid])  # Odometria and Freni
    assert clauses() == ["3.5.1.1", "3.5.2.1"]
    assert reader.count.text() == "2 voci"
    reader.go_to(e["c4"].uuid)  # from outside: the filters that hide it are removed
    assert reader.scope.currentIndex() == 0 and "3.5.2.2" in clauses()
    reader.close()  # not left open on the screen for the next tests (e.g. those with the mouse)
    reader.deleteLater()
    app.processEvents()
    p.close()


def test_the_clauses_of_the_team_in_a_section_of_another_team_are_highlighted(app, tmp_path):
    from types import SimpleNamespace
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem
    from arcadia_tool.ui.srs_reader import TEAM_CLAUSE_BG, SrsReader

    p, e = build_srs(tmp_path)
    users = {"mario": SimpleNamespace(id="b" * 32, full_name="Mario Rossi"),  # FBK: Odometria, Freni
             "anna": SimpleNamespace(id="a" * 32, full_name="Anna Bianchi")}
    rfi = p.model.get(e["rfi"].uuid)
    rfi.set("members", [{"name": "Anna Bianchi", "account": "a" * 32}])  # RFI: Radio
    user = [users["anna"]]
    reader = SrsReader(p, user_of=lambda: user[0])
    reader.resize(1000, 600)
    reader.show()
    app.processEvents()
    # Anna (Radio): 3.5.2.2 passed to Radio in 3.5.2 of Freni; 3.5.1.x are in her own section, not highlighted.
    assert reader.delegate.team_clauses == {e["c4"].uuid}
    user[0] = users["mario"]  # FBK: Odometria contributes to 3.5.1 (its section), Freni has 3.5.2: nothing mixed
    reader.user_changed()
    assert reader.delegate.team_clauses == set()
    user[0] = None
    reader.user_changed()
    assert reader.delegate.team_clauses == set()
    user[0] = users["anna"]
    reader.user_changed()
    row = next(i for i, x in enumerate(reader.model.elements) if x.uuid == e["c4"].uuid)
    index = reader.model.index(row)
    option = QStyleOptionViewItem()
    option.rect = reader.view.visualRect(index).translated(0, -reader.view.visualRect(index).y())
    image = QImage(option.rect.width(), option.rect.height(), QImage.Format_RGB32)
    image.fill(0xFFFFFF)
    painter = QPainter(image)
    reader.delegate.paint(painter, option, index)
    painter.end()
    assert image.pixelColor(option.rect.width() - 5, 2).name() == TEAM_CLAUSE_BG.lower()  # only the background
    reader.close()
    reader.deleteLater()
    app.processEvents()
    p.close()


def test_the_highlight_can_be_turned_off_and_the_pick_looks_like_a_combo(app, tmp_path):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QComboBox as Combo
    from arcadia_tool.ui.srs_reader import BY_DOMAINS, SrsReader

    p, e = build_srs(tmp_path)
    p.model.get(e["rfi"].uuid).set("members", [{"name": "Anna Bianchi", "account": "a" * 32}])
    anna = SimpleNamespace(id="a" * 32, full_name="Anna Bianchi")
    reader = SrsReader(p, user_of=lambda: anna)
    reader.resize(1000, 600)
    reader.show()
    app.processEvents()
    box = reader.highlight_team
    assert box.text() == "Evidenzia requisiti team" and box.isChecked()
    row = reader.show_headings.parentWidget().layout()
    assert reader.delegate.team_clauses == {e["c4"].uuid}
    box.setChecked(False)
    assert reader.delegate.team_clauses == set()
    reader.refresh()
    assert reader.delegate.team_clauses == set()  # also after the filters change
    box.setChecked(True)
    assert reader.delegate.team_clauses == {e["c4"].uuid}
    assert isinstance(reader.scope_pick, Combo)  # the same look as the other drop-down lists
    reader.scope.setCurrentIndex(reader.scope.findData(BY_DOMAINS))
    assert reader.scope_pick.text() == "Scegli i domini…"
    reader.scope_pick.showPopup()
    assert reader.scope_pick.menu_.isVisible()
    reader.scope_pick.menu_.actions()[0].trigger()  # ticked: the list stays open
    assert reader.scope_pick.text() == "DF01 Radio" and reader.scope_pick.menu_.isVisible()
    reader.scope_pick.hidePopup()
    assert row is not None
    reader.close()
    reader.deleteLater()
    app.processEvents()
    p.close()
