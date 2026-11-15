"""A functional chain composed in its view: «Nuova catena funzionale…» from «Viste grafiche» creates the chain and
its two views; in the view of the chain a function dropped is a new step (what it does asked), a connector between
two steps is the exchange between them, from an external actor the trigger; the menu of a step changes its row. The
path is the one of the sheet SA-7: the views know a step by the stable key of its row."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from arcadia_tool.model import chains
from arcadia_tool.model import diagrams as dg
from arcadia_tool.model.element import ROW_KEY, Element
from arcadia_tool.model.schema import DIAGRAM_CHAIN, DIAGRAM_SCENARIO, INTERNAL, PATH, SCENARIO
from arcadia_tool.storage.project import Project
from arcadia_tool.ui import diagrams as ud


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def build(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    e = {"df08": p.new_element("domain", id="DF08", name="Modi"),
         "df07": p.new_element("domain", id="DF07", name="Freni"),
         "pwr": p.new_element("external_actor", id="PWR", name="Alimentazione")}
    e["sf08"] = p.new_element("system_function", id="SF-DF08-01", name="Gestire l'avvio", domain=e["df08"].uuid)
    e["sf07"] = p.new_element("system_function", id="SF-DF07-01", name="Provare i freni", domain=e["df07"].uuid)
    e["ei"] = p.new_element("exchange_item", id="EI-RichiestaTest", name="Richiesta di test", nature="OPERATION")
    e["fe"] = p.new_element("functional_exchange", source=e["sf08"].uuid, target=e["sf07"].uuid,
                            exchange_item=e["ei"].uuid, nature="OPERATION")
    p.save()
    return p, e


def steps_of(chain):
    return chain.get("steps") or []


def test_the_rows_of_the_path_have_a_stable_key(tmp_path):
    p, e = build(tmp_path)
    chain = p.new_element("functional_chain", title="Test", steps=[{"function": e["sf08"].uuid, "what": "A"},
                                                                    {"function": e["sf07"].uuid, "what": "B"}])
    keys = [r[ROW_KEY] for r in steps_of(chain)]
    assert len(set(keys)) == 2 and all(not k.isdigit() for k in keys)
    p.update(chain)
    assert [r[ROW_KEY] for r in steps_of(chain)] == keys  # kept
    rows = steps_of(chain)
    rows.append(dict(rows[0]))  # a copy of a row: a key of its own
    p.update(chain)
    assert len({r[ROW_KEY] for r in steps_of(chain)}) == 3
    # The key is not a change shown in the comparison of versions.
    from arcadia_tool.diff.semantic import _diff_rows
    from arcadia_tool.model.schema import KINDS_BY_NAME
    columns = KINDS_BY_NAME["functional_chain"].field("steps").columns
    assert _diff_rows([{"what": "A"}], [{"what": "A", ROW_KEY: "r1234567"}], columns) == []


def test_a_project_of_an_earlier_version_gets_the_keys_and_its_views_follow(tmp_path):
    p, e = build(tmp_path)
    chain = Element("functional_chain", values={"id": "FC-Test", "title": "Test", "steps": [
        {"function": e["sf08"].uuid, "what": "A"}, {"what": "Attesa: x"}, {"function": e["sf07"].uuid, "what": "B"}]})
    view = Element("diagram", values={"name": "V", "diagram_type": DIAGRAM_CHAIN, "chain": chain.uuid,
                                      "layout": {"step:0": "40,60", "step:2": "", "step:9": ""}})
    p.model.add(chain)
    p.model.add(view)
    p._migrate()
    rows = steps_of(chain)
    assert all(r.get(ROW_KEY) for r in rows)
    assert view.get("layout") == {dg.step_key(rows[0]): "40,60", dg.step_key(rows[2]): "", "step:9": ""}
    assert [s.what for s in dg.shown_steps(p.model, view)] == ["A", "B"]
    assert dg.missing(p.model, view) == ["step:9"]  # no longer in the chain


def test_the_sheet_keeps_the_keys_of_the_rows(app, tmp_path):
    from arcadia_tool.ui.element_editor import ElementEditor, TableWidget
    p, e = build(tmp_path)
    chain = p.new_element("functional_chain", title="Test", steps=[{"function": e["sf08"].uuid, "what": "A"}])
    key = steps_of(chain)[0][ROW_KEY]
    editor = ElementEditor()
    editor.edit(p, chain, editing=True)
    table = next(w for w in editor.findChildren(TableWidget) if w.row_keys)
    assert table.value()[0][ROW_KEY] == key
    table._add_clicked()  # a row added in the sheet: its key at once
    rows = table.value()
    assert rows[0][ROW_KEY] == key and rows[1][ROW_KEY] and rows[1][ROW_KEY] != key


def compose(app, tmp_path, monkeypatch):
    """The main window, a chain created from «Viste grafiche» and its view open."""
    from arcadia_tool.ui import main_window as mw
    p, e = build(tmp_path)
    monkeypatch.setattr(ud.NewChainDialog, "exec", lambda self: self.title.setText("Isolamento dell'EVC") or True)
    window = mw.MainWindow()
    window._set_project(p)
    chain = window.tree.create_chain()
    page = window.pages.currentWidget()
    return p, e, window, chain, page


def test_a_new_chain_from_the_views_opens_its_view_to_compose_it(app, tmp_path, monkeypatch):
    p, e, window, chain, page = compose(app, tmp_path, monkeypatch)
    assert chain.get("id") == "FC-IsolamentoEVC" and not steps_of(chain)
    views = [v for v in p.model.of_kind("diagram") if v.get("chain") == chain.uuid]
    assert [v.get("diagram_type") for v in views] == [DIAGRAM_CHAIN]  # one view: its path, or its scenario
    assert isinstance(page, ud.DiagramPage) and page.diagram_type == DIAGRAM_CHAIN and page.path_chain() is chain
    assert not p.is_modified  # saved with the project
    # The list: the functions (a new step) and the external actors; the tools: the connectors.
    groups = {a.group for a in dg.addable(p.model, page.working())}
    assert "Attori esterni" in groups and "Nuovo passo · DF08 · Modi" in groups
    assert page.side_tabs.isTabVisible(0) and not page.chain_hint.isHidden()


def test_functions_dropped_are_the_steps_of_the_path(app, tmp_path, monkeypatch):
    p, e, window, chain, page = compose(app, tmp_path, monkeypatch)
    answers = iter([("Chiede il test", "1"), ("Riceve l'esito", ""), ("Prova i freni", "")])

    def ask(self):
        what, cycle = next(answers)
        self.what.setPlainText(what)
        self.cycle.setText(cycle)
        return True
    monkeypatch.setattr(ud.StepDialog, "exec", ask)
    first = page.add(e["sf08"].uuid, QPointF(100, 100))
    third = page.add(e["sf08"].uuid, QPointF(600, 100))
    assert [r["what"] for r in steps_of(chain)] == ["Chiede il test", "Riceve l'esito"]
    assert steps_of(chain)[0]["cycle"] == "1" and page.placed[first] == (100 - dg.STEP_W / 2, 100 - dg.STEP_H / 2)
    # Two steps without an exchange: independent, no arrow between them.
    assert not any(getattr(a, "steps", None) for a in page.arrows)
    # Dropped on the line between them: between them.
    middle = (page.items[first].sceneBoundingRect().center() + page.items[third].sceneBoundingRect().center()) / 2
    second = page.add(e["sf07"].uuid, middle)
    assert [r["what"] for r in steps_of(chain)] == ["Chiede il test", "Prova i freni", "Riceve l'esito"]
    assert [s.key for s in dg.shown_steps(p.model, page.working())] == [first, second, third]
    assert chain.get("domains") == [e["df08"].uuid, e["df07"].uuid]  # the domains of its functions
    # In the model at once, and in the view as saved (its scenario shows them too).
    assert chain.uuid not in p.pending()
    assert len(dg.shown_steps(p.model, p.model.get(page.view.uuid))) == 3
    # Ctrl+Z: the last step out of the path again.
    assert page.undo()
    assert [r["what"] for r in p.model.get(chain.uuid).get("steps")] == ["Chiede il test", "Riceve l'esito"]
    assert second not in page.placed


def test_connectors_link_the_steps_with_their_exchanges(app, tmp_path, monkeypatch):
    p, e, window, chain, page = compose(app, tmp_path, monkeypatch)
    monkeypatch.setattr(ud.StepDialog, "exec", lambda self: self.what.setPlainText("Fa") or True)
    a = page.add(e["sf08"].uuid)
    b = page.add(e["sf07"].uuid)
    page.set_connector("OPERATION")
    # Between their functions there is an exchange already: reused.
    monkeypatch.setattr(ud.ExchangeChoiceDialog, "exec", lambda self: True)
    fe = page.connect_elements(a, b)
    assert fe is e["fe"]
    rows = steps_of(chain)
    assert rows[0]["exchange"] == fe.uuid and rows[1]["input"] == fe.uuid
    assert rows[0]["data"] == "EI-RichiestaTest" and rows[0]["nature"] == "OPERATION"
    arrow = next(x for x in page.arrows if getattr(x, "steps", None) == (a, b))
    assert arrow.key == fe.uuid  # a double click opens it
    # The trigger: from an external actor to the first step, a new exchange.
    page.add(e["pwr"].uuid)
    assert page._kinds[e["pwr"].uuid] == "external_actor"

    def new_exchange(self):
        self.name.setText("Evento di accensione")
        return True
    monkeypatch.setattr(ud.NewExchangeDialog, "exec", new_exchange)
    trigger = page.connect_elements(e["pwr"].uuid, a)
    assert trigger.get("source") == e["pwr"].uuid and steps_of(chain)[0]["input"] == trigger.uuid
    assert any(x.key == trigger.uuid for x in page.arrows)  # drawn from the actor
    sc = dg.scenario(p.model, page.working())
    assert [m.ident for m in sc.messages] == [trigger.get("id"), fe.get("id"), ""]
    # Two steps of the same function: no exchange.
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    c = page.add(e["sf07"].uuid)
    assert page.connect_elements(b, c) is None
    # The exchange out of the path (not out of the model).
    page._edit_path(lambda rows: chains.unlink(rows, page._row_key(a), page._row_key(b)), "x")
    assert "exchange" not in steps_of(chain)[0] and "input" not in steps_of(chain)[1]
    assert p.model.get(fe.uuid) is not None


def test_the_menu_of_a_step_changes_its_row(app, tmp_path, monkeypatch):
    p, e, window, chain, page = compose(app, tmp_path, monkeypatch)
    monkeypatch.setattr(ud.StepDialog, "exec", lambda self: self.what.setPlainText("Fa") or True)
    a = page.add(e["sf08"].uuid)
    b = page.add(e["sf07"].uuid)
    page.set_internal(b, True)
    assert steps_of(chain)[1]["nature"] == INTERNAL
    monkeypatch.setattr(ud.QInputDialog, "getText", lambda *args, **kw: ("fine del test", True))
    page.insert_wait(a)
    assert [r["what"] for r in steps_of(chain)] == ["Fa", "Attesa: fine del test", "Fa"]
    assert [s.number for s in dg.shown_steps(p.model, page.working())] == ["1", "2"]  # the wait is not drawn
    page.move_step(b, -1)
    page.move_step(b, -1)
    assert [r.get("function") for r in steps_of(chain)] == [e["sf07"].uuid, e["sf08"].uuid, None]
    assert not page.move_step(b, -1)  # already the first
    monkeypatch.setattr(ud.StepDialog, "exec", lambda self: self.what.setPlainText("Prova") or
                        self.cycle.setText("2") or True)
    page.edit_step(b)
    assert steps_of(chain)[0]["what"] == "Prova" and steps_of(chain)[0]["cycle"] == "2"
    page.remove_step(a, ask=False)
    assert [r["what"] for r in steps_of(chain)] == ["Prova", "Attesa: fine del test"]
    assert a not in page.placed and not page.notice.isVisible()
    assert a not in (p.model.get(page.view.uuid).get("layout") or {})


def test_a_chain_deleted_takes_its_views_with_it(app, tmp_path, monkeypatch):
    p, e, window, chain, page = compose(app, tmp_path, monkeypatch)
    views = p.views_of_chain(chain.uuid)
    assert len(views) == 1
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda parent, title, text, *a: asked.append(text) or
                        QMessageBox.Yes)
    window.tree.delete_element(chain)
    assert "Catena funzionale" in asked[0]  # said before
    assert p.model.get(chain.uuid) is None and all(p.model.get(v.uuid) is None for v in views)
    assert all(v.uuid not in window.tree._view_items for v in views)  # out of «Viste grafiche»
    assert window.pages.indexOf(page) < 0  # its open tab closed


def test_the_arrow_between_two_steps_turned_round(app, tmp_path, monkeypatch):
    p, e, window, chain, page = compose(app, tmp_path, monkeypatch)
    monkeypatch.setattr(ud.StepDialog, "exec", lambda self: self.what.setPlainText("Fa") or True)
    a = page.add(e["sf08"].uuid)
    b = page.add(e["sf07"].uuid)
    page.set_connector("OPERATION")
    monkeypatch.setattr(ud.ExchangeChoiceDialog, "exec", lambda self: True)
    page.connect_elements(a, b)  # SF-DF08-01 → SF-DF07-01
    page.set_connector(None)
    # The arrow between the steps: selected with a click, its menu told by its tooltip.
    from PySide6.QtWidgets import QGraphicsItem
    arrow = next(x for x in page.arrows if getattr(x, "steps", None) == (a, b))
    assert arrow.flags() & QGraphicsItem.ItemIsSelectable and arrow.acceptHoverEvents()
    assert "clic destro: inverti il verso" in arrow.toolTip()
    arrow.setSelected(True)
    assert page.scene.selectedItems() == [arrow]
    page.delete_selected()  # Canc: nothing out of the model, nor of the path
    assert steps_of(chain)[0]["exchange"] == e["fe"].uuid and p.model.get(e["fe"].uuid) is not None
    # No exchange from SF-DF07-01 to SF-DF08-01: a new one is asked, «Annulla» leaves them without.
    asked = []
    monkeypatch.setattr(ud.NewExchangeDialog, "exec", lambda self: asked.append(self) and False)
    assert page.reverse_steps(a, b)
    rows = steps_of(p.model.get(chain.uuid))
    assert [r["function"] for r in rows] == [e["sf07"].uuid, e["sf08"].uuid]
    assert not any(r.get("exchange") or r.get("input") for r in rows) and asked
    assert p.model.get(e["fe"].uuid) is not None  # out of the path, not of the model
    assert [s.key for s in dg.shown_steps(p.model, page.working())] == [b, a]
    # Ctrl+Z: as it was, with its exchange.
    assert page.undo()
    rows = steps_of(p.model.get(chain.uuid))
    assert [r["function"] for r in rows] == [e["sf08"].uuid, e["sf07"].uuid] and rows[0]["exchange"] == e["fe"].uuid
    # An exchange in the opposite direction in the model: chosen for the new order.
    back = p.new_element("functional_exchange", source=e["sf07"].uuid, target=e["sf08"].uuid,
                         exchange_item=e["ei"].uuid, nature="OPERATION")
    assert page.reverse_steps(a, b)
    rows = steps_of(p.model.get(chain.uuid))
    assert rows[0]["exchange"] == back.uuid and rows[1]["input"] == back.uuid


def test_reversing_two_steps_unlinks_their_neighbours(tmp_path):
    rows = [{"key": "r1", "function": "f1", "exchange": "x1"}, {"key": "r2", "function": "f2", "input": "x1",
                                                                 "exchange": "x2"},
            {"key": "r3", "function": "f3", "input": "x2", "exchange": "x3"}, {"key": "r4", "function": "f4",
                                                                                "input": "x3"}]
    assert chains.reverse(rows, "r2", "r3") == ["x2", "x1", "x3"]
    assert [r["key"] for r in rows] == ["r1", "r3", "r2", "r4"]
    assert not any(r.get("exchange") or r.get("input") for r in rows)
    assert chains.reverse(rows, "r2", "r9") is False


def test_the_steps_stay_in_the_view_closed_without_saving_it(app, tmp_path, monkeypatch):
    p, e, window, chain, page = compose(app, tmp_path, monkeypatch)
    monkeypatch.setattr(ud.StepDialog, "exec", lambda self: self.what.setPlainText("Fa") or True)
    a = page.add(e["sf07"].uuid, QPointF(100, 100))
    b = page.add(e["sf08"].uuid, QPointF(400, 100))
    view = p.model.get(page.view.uuid)
    assert {a, b} <= set(view.get("layout"))  # in the view as saved, at once
    page.discard_changes(remember=False)  # closed without saving: the tool places them
    assert [s.key for s in dg.shown_steps(p.model, page.working())] == [a, b]


def test_a_view_left_empty_by_an_earlier_version_gets_its_steps_back(tmp_path):
    p, e = build(tmp_path)
    chain = p.new_element("functional_chain", title="Accensione",
                          steps=[{"function": e["sf07"].uuid, "what": "A"}, {"what": "Attesa: x"},
                                 {"function": e["sf08"].uuid, "what": "B"}])
    empty = p.new_element("diagram", name="Accensione", diagram_type=DIAGRAM_CHAIN, chain=chain.uuid,
                          layout={})
    some = p.new_element("diagram", name="Solo uno", diagram_type=DIAGRAM_SCENARIO, chain=chain.uuid,
                         layout={dg.step_key(chain.get("steps")[0]): ""})
    p.save()
    again = Project.open(p.path)
    rows = again.model.get(chain.uuid).get("steps")
    assert [s.key for s in dg.shown_steps(again.model, again.model.get(empty.uuid))] == [
        dg.step_key(rows[0]), dg.step_key(rows[2])]
    assert list(again.model.get(some.uuid).get("layout")) == [dg.step_key(rows[0])]  # a step taken out stays out
    # Not the same steps as the view of the chain: a view of the chain, drawn as its scenario.
    assert again.model.get(some.uuid).get("diagram_type") == DIAGRAM_CHAIN
    assert dg.drawing(again.model.get(some.uuid)) == SCENARIO


def test_the_scenarios_of_an_earlier_version_merged_in_the_views_of_their_chains(tmp_path):
    p, e = build(tmp_path)
    rows = [{"function": e["sf07"].uuid, "what": "A"}, {"function": e["sf08"].uuid, "what": "B"}]
    chain = p.new_element("functional_chain", title="Accensione", steps=rows)
    keys = dg.new_view_layout(p.model, DIAGRAM_CHAIN, chain.uuid)
    path = p.new_element("diagram", name="Accensione", diagram_type=DIAGRAM_CHAIN, chain=chain.uuid,
                         layout={k: f"{100 * i},60" for i, k in enumerate(keys)})
    twin = p.new_element("diagram", name="Accensione", diagram_type=DIAGRAM_SCENARIO, chain=chain.uuid,
                         layout=dict(keys))
    by_function = p.new_element("diagram", name="Per funzione", diagram_type=DIAGRAM_SCENARIO, chain=chain.uuid,
                                layout=dict(keys), level="Per funzione")
    orphan = p.new_element("diagram", name="Vecchia", diagram_type=DIAGRAM_SCENARIO, chain="gone", layout={})
    p.save()
    again = Project.open(p.path)
    m = again.model
    # The same steps at the same level: one view; another level: a view of the chain drawn as a scenario.
    assert m.get(twin.uuid) is None and m.get(orphan.uuid) is None
    assert dg.drawing(m.get(path.uuid)) == PATH and dg.positions(m.get(path.uuid)) == dg.positions(path)
    assert m.get(by_function.uuid).get("diagram_type") == DIAGRAM_CHAIN and dg.is_scenario(m.get(by_function.uuid))
    assert "1 unite alla vista della loro catena" in again.migration_notes[0]
    assert "1 di catene non più nel modello eliminate" in again.migration_notes[0]
    again.save()
    assert not Project.open(p.path).migration_notes  # once


def test_one_view_drawn_as_its_path_or_its_scenario(app, tmp_path, monkeypatch):
    p, e, window, chain, page = compose(app, tmp_path, monkeypatch)
    monkeypatch.setattr(ud.StepDialog, "exec", lambda self: self.what.setPlainText("Fa") or True)
    a = page.add(e["sf08"].uuid)
    b = page.add(e["sf07"].uuid)
    page.set_connector("OPERATION")
    monkeypatch.setattr(ud.ExchangeChoiceDialog, "exec", lambda self: True)
    page.connect_elements(a, b)
    page.set_connector(None)
    assert not page.drawing.isHidden() and [page.drawing.itemText(i) for i in range(2)] == [PATH, SCENARIO]
    # The step selected stays selected in the other drawing: its message.
    page.select_steps([a])
    page.drawing.setCurrentText(SCENARIO)
    assert page.diagram_type == DIAGRAM_SCENARIO and page.selected_steps() == [a]
    assert not page.legend.isHidden() and page.side_by_side.isHidden()
    assert not page.side_tabs.isTabVisible(0)  # no composing on the canvas of the scenario
    # The list of the elements: only the steps not in the view (no functions to drop).
    assert all(x.kind == "step" for x in dg.addable(p.model, page.working()))
    page.save_view()
    saved = p.model.get(page.view.uuid)
    assert saved.get("drawing") == SCENARIO and saved.get("diagram_type") == DIAGRAM_CHAIN
    # Back to the path: its places kept.
    placed = dict(page.placed)
    page.drawing.setCurrentText(PATH)
    assert page.path_chain() is chain and page.placed == placed and page.selected_steps() == [a]
    # Its scenario at its side, drawn again at each change.
    page.side_by_side.setChecked(True)
    side = page.companion
    assert side is not None and side.isVisibleTo(page) and side.diagram_type == DIAGRAM_SCENARIO
    assert side.header.isHidden() and len(side.arrows) == len(dg.scenario(p.model, page.working()).messages)
    page.remove_step(b, ask=False)
    assert len(side.arrows) == len(dg.scenario(p.model, page.working()).messages)
    assert not side.dirty
    page.drawing.setCurrentText(SCENARIO)
    assert not side.isVisibleTo(page)
    page.side_by_side.setChecked(False)


def test_the_steps_by_cycle_in_their_tab(app, tmp_path, monkeypatch):
    p, e, window, chain, page = compose(app, tmp_path, monkeypatch)
    answers = iter([("Chiede il test", "0"), ("Prova i freni", "0"), ("Riceve l'esito", "1")])

    def ask(self):
        what, cycle = next(answers)
        self.what.setPlainText(what)
        self.cycle.setText(cycle)
        return True
    monkeypatch.setattr(ud.StepDialog, "exec", ask)
    a = page.add(e["sf08"].uuid)
    b = page.add(e["sf07"].uuid)
    c = page.add(e["sf08"].uuid)
    monkeypatch.setattr(ud.QInputDialog, "getText", lambda *args, **kw: ("fine del test", True))
    page.insert_wait(b)
    assert page.side_tabs.isTabVisible(2) and page.activity.buttons[2].isVisibleTo(page)
    tree = page.steps_list
    tops = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    assert [t.text(0) for t in tops] == ["Ciclo 0", "Attesa: fine del test", "Ciclo 1"]
    assert [tops[0].child(i).text(0) for i in range(tops[0].childCount())] == [
        "1 · DF08  Chiede il test", "2 · DF07  Prova i freni"]
    third = tops[2].child(0)
    page._step_chosen(third)  # a click: the step selected in the view
    assert page.items[c].isSelected() and not page.items[a].isSelected()
    page.remove([c])  # out of the view: still listed, in grey
    third = page.steps_list.topLevelItem(2).child(0)
    assert "Non nella vista" in third.toolTip(0)
    # Opened again: a view with steps starts from them.
    from arcadia_tool.ui.diagrams import DiagramPage
    again = DiagramPage(p, page.view)
    assert again.side_tabs.currentWidget() is again.steps_panel


def test_the_steps_dragged_in_their_tab_change_order_and_cycle(app, tmp_path, monkeypatch):
    p, e, window, chain, page = compose(app, tmp_path, monkeypatch)
    answers = iter([("A", "0"), ("B", "0"), ("C", "0"), ("D", "1")])

    def ask(self):
        what, cycle = next(answers)
        self.what.setPlainText(what)
        self.cycle.setText(cycle)
        return True
    monkeypatch.setattr(ud.StepDialog, "exec", ask)
    a, b, c, d = (page.add(e[f].uuid) for f in ("sf08", "sf07", "sf08", "sf07"))
    monkeypatch.setattr(ud.QInputDialog, "getText", lambda *args, **kw: ("fine del ciclo", True))
    page.insert_wait(c)

    def order():
        return [(r["what"], r.get("cycle", "")) for r in steps_of(p.model.get(chain.uuid))]
    # In the same cycle: C before A.
    assert page.move_step_to(c, a, False, "0")
    assert order() == [("C", "0"), ("A", "0"), ("B", "0"), ("Attesa: fine del ciclo", ""), ("D", "1")]
    # To another cycle: A after D, in cycle 1.
    assert page.move_step_to(a, d, True, "1")
    assert order() == [("C", "0"), ("B", "0"), ("Attesa: fine del ciclo", ""), ("D", "1"), ("A", "1")]
    assert not page.move_step_to(a, d, True, "1")  # already there
    tree = page.steps_list
    tops = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    assert [t.text(0) for t in tops] == ["Ciclo 0", "Attesa: fine del ciclo", "Ciclo 1"]
    # Where a drop goes: on a step (above, below), on a cycle (its end), around a wait.
    from PySide6.QtWidgets import QAbstractItemView as V
    first_of_1 = tops[2].child(0)
    assert tree._placement(first_of_1, V.AboveItem) == (d, False, "1")
    assert tree._placement(tops[0], V.OnItem) == (b, True, "0")  # the end of cycle 0
    assert tree._placement(tops[1], V.AboveItem) == (tops[1].data(0, ud.WAIT_KEY_ROLE), False, "0")
    assert tree._placement(tops[1], V.BelowItem) == (tops[1].data(0, ud.WAIT_KEY_ROLE), True, "1")
    # A drag on the tree: D at the end of cycle 0.
    tree.setCurrentItem(first_of_1)
    monkeypatch.setattr(tree, "itemAt", lambda _pos: tops[0])
    monkeypatch.setattr(tree, "dropIndicatorPosition", lambda: V.OnItem)
    from PySide6.QtCore import QMimeData, QPointF as P
    from PySide6.QtGui import QDropEvent
    tree.dropEvent(QDropEvent(P(5, 5), Qt.MoveAction, QMimeData(), Qt.LeftButton, Qt.NoModifier))
    assert order() == [("C", "0"), ("B", "0"), ("D", "0"), ("Attesa: fine del ciclo", ""), ("A", "1")]
    # Ctrl+Z: as it was.
    assert page.undo()
    assert order() == [("C", "0"), ("B", "0"), ("Attesa: fine del ciclo", ""), ("D", "1"), ("A", "1")]


def test_the_steps_dragged_in_the_scenario_too(app, tmp_path, monkeypatch):
    p, e, window, chain, page = compose(app, tmp_path, monkeypatch)
    answers = iter([("A", "0"), ("B", "0"), ("C", "1")])

    def ask(self):
        what, cycle = next(answers)
        self.what.setPlainText(what)
        self.cycle.setText(cycle)
        return True
    monkeypatch.setattr(ud.StepDialog, "exec", ask)
    a, b, c = (page.add(e[f].uuid) for f in ("sf08", "sf07", "sf08"))
    from PySide6.QtWidgets import QAbstractItemView
    scenario = page
    scenario.drawing.setCurrentText(SCENARIO)  # the same view, drawn as its scenario
    assert scenario.diagram_type == DIAGRAM_SCENARIO
    assert scenario.path_chain() is None and scenario.steps_chain() is chain  # no composing on its canvas
    assert scenario.steps_list.dragDropMode() == QAbstractItemView.InternalMove
    assert scenario.move_step_to(c, a, False, "0")  # C first, in cycle 0
    rows = steps_of(p.model.get(chain.uuid))
    assert [(r["what"], r.get("cycle")) for r in rows] == [("C", "0"), ("A", "0"), ("B", "0")]
    # The chain and its views follow; Ctrl+Z in the scenario puts it back.
    assert [s.key for s in dg.shown_steps(p.model, p.model.get(page.view.uuid))] == [c, a, b]
    assert scenario.undo()
    assert [r["what"] for r in steps_of(p.model.get(chain.uuid))] == ["A", "B", "C"]
