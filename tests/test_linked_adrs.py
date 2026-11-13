"""«ADR collegate»: every ADR can refer to other ADR, chosen with ticks in a window listing all the others; unticked,
they are no longer linked."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from arcadia_tool.model.schema import ADR_OTHER, ADR_SECTION
from arcadia_tool.storage.project import Project
from arcadia_tool.ui import element_editor
from arcadia_tool.ui.element_editor import ElementEditor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_the_adr_linked_are_chosen_and_unchosen_with_ticks(app, tmp_path, monkeypatch):
    p = Project.create(tmp_path / "p", "Prova")
    a1 = p.new_element("adr", id="ADR-001", title="Prima", adr_type=ADR_SECTION, status="Proposta")
    a2 = p.new_element("adr", id="ADR-002", title="Seconda", adr_type=ADR_OTHER, status="Decisa")
    a10 = p.new_element("adr", id="ADR-010", title="Decima", adr_type=ADR_OTHER, status="Proposta")
    editor = ElementEditor()
    editor.edit(p, a1, editing=True)
    widget = editor.widgets["linked_adrs"]
    assert editor.field_labels["linked_adrs"].text() == "ADR collegate"
    seen = []

    def tick(wanted):
        def run(dialog):
            seen.append([dialog.list.item(i).text() for i in range(dialog.list.count())])
            for i in range(dialog.list.count()):
                item = dialog.list.item(i)
                item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in wanted else Qt.Unchecked)
            return True
        return run
    monkeypatch.setattr(element_editor.RefPicker, "exec", tick({a2.uuid, a10.uuid}))
    widget._pick()
    # All the others, by ID (not the ADR itself), with their type and status.
    assert seen[0] == ["ADR-002 · Seconda  —  Altro / decisione trasversale · Decisa",
                       "ADR-010 · Decima  —  Altro / decisione trasversale · Proposta"]
    assert widget.value() == [a2.uuid, a10.uuid]
    editor.save_changes()
    assert a1.get("linked_adrs") == [a2.uuid, a10.uuid]
    # Unticked: no longer linked.
    editor.start_editing()
    monkeypatch.setattr(element_editor.RefPicker, "exec", tick({a10.uuid}))
    editor.widgets["linked_adrs"]._pick()
    editor.save_changes()
    assert a1.get("linked_adrs") == [a10.uuid]
    p.close()


def test_every_type_has_them_but_not_the_templates():
    from arcadia_tool.model.adr import common_fields, type_fields
    from arcadia_tool.model.element import Element
    from arcadia_tool.model.schema import ADR_TYPE_LABELS, KINDS_BY_NAME

    field = KINDS_BY_NAME["adr"].field("linked_adrs")
    for adr_type in ADR_TYPE_LABELS:
        assert field.applies(Element("adr", values={"adr_type": adr_type}))
        names = [f.name for f in type_fields(adr_type) + common_fields(adr_type)]
        assert "linked_adrs" not in names  # the templates X-1 do not change
