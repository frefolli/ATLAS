"""The approval of the deletion of a functional domain: the elements that would be left orphan, each with what to do
with it (see model.domain_deletion), chosen by the Design Authority before the domain is removed."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout)

from arcadia_tool.model.domain_deletion import DELETE, KEEP, deletable, orphans, second_references
from arcadia_tool.model.element import natural_key
from arcadia_tool.ui.element_editor import card
from arcadia_tool.ui.theme import MUTED, icon

UUID_ROLE = Qt.UserRole


def orphan_text(model, element):
    """An orphan as listed: an SRS item by its number and the start of its text, the others by their label."""
    if element.kind == "requirement":
        text = " ".join((element.get("text") or element.get("title") or "").split())
        return f"{element.get('id') or ''}  {text[:90]}{'…' if len(text) > 90 else ''}".strip()
    return model.label(element)


class DomainDeletionDialog(QDialog):
    """«Approva ed elimina il dominio»: the orphans grouped by kind, each with a choice (also one for the whole
    group): to stay without a domain, to pass to another domain, or to be deleted (a function or a derived
    requirement nothing else uses). The mentions of second order are said, and removed."""

    def __init__(self, project, domain, parent=None):
        super().__init__(parent)
        self.project, self.domain = project, domain
        model = project.model
        self.setWindowTitle("Approva ed elimina il dominio")
        self.resize(900, 620)
        self.others = sorted((d for d in model.of_kind("domain") if d.uuid != domain.uuid),
                             key=lambda d: natural_key(d.get("id") or d.get("name") or ""))
        header, header_layout = card()
        header_layout.addWidget(QLabel(f"Eliminare il dominio «{model.label(domain)}»?", objectName="elementTitle"))
        self.groups = orphans(model, domain.uuid)
        count = sum(len(elements) for _group, elements in self.groups)
        hint = QLabel(
            ("Questi elementi hanno il dominio come proprio e resterebbero orfani: scegli per ognuno cosa farne, "
             "o per un intero gruppo dalla sua riga. «Elimina» è possibile solo per funzioni e requisiti derivati "
             "che nessun altro elemento usa." if count else "Nessun elemento del modello resta orfano.")
            + " Il dominio viene poi eliminato dal modello e l'ADR risulta decisa.", objectName="muted")
        hint.setWordWrap(True)
        header_layout.addWidget(hint)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Elemento", "Cosa farne"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.tree.header().resizeSection(1, 300)
        self.tree.header().setStretchLastSection(False)
        self.combos = {}  # uuid of an orphan → its combo
        bold = QFont()
        bold.setBold(True)
        for group, elements in self.groups:
            top = QTreeWidgetItem(self.tree, [f"{group.title} ({len(elements)})"])
            top.setFont(0, bold)
            can_delete = [e for e in elements if deletable(model, e, domain.uuid)]
            all_combo = self._combo(group, bool(can_delete), "Per tutti: ")
            self.tree.setItemWidget(top, 1, all_combo)
            children = []
            for element in elements:
                item = QTreeWidgetItem(top, [orphan_text(model, element)])
                item.setData(0, UUID_ROLE, element.uuid)
                item.setToolTip(0, model.label(element))
                combo = self._combo(group, element in can_delete)
                self.tree.setItemWidget(item, 1, combo)
                self.combos[element.uuid] = combo
                children.append(combo)
            all_combo.activated.connect(lambda _i, source=all_combo, targets=children: self._apply_all(source,
                                                                                                    targets))
            top.setExpanded(True)
        second = second_references(model, domain.uuid)
        mentions = QLabel(objectName="muted")
        mentions.setWordWrap(True)
        if second:
            names = ", ".join((e.get("id") or model.label(e)) for e in second[:15]) + (
                f" e altri {len(second) - 15}" if len(second) > 15 else "")
            mentions.setText(f"Il dominio viene tolto anche dove è solo citato (come contributore, come escluso, "
                             f"tra i domini di un team): {names}.")
        mentions.setVisible(bool(second))
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton(icon("mdi6.delete-outline", "white"), "Elimina il dominio")
        self.ok.setProperty("primary", True)
        self.ok.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.ok)
        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(self.tree, 1)
        layout.addWidget(mentions)
        layout.addLayout(buttons)
        self.tree.setVisible(bool(self.groups))

    def _combo(self, group, can_delete, prefix=""):
        model = self.project.model
        combo = QComboBox()
        combo.addItem(f"{prefix}{group.keep}", KEEP)
        for d in self.others:
            combo.addItem(f"{prefix}Passa a {model.label(d)}", d.uuid)
        if can_delete:
            combo.addItem(f"{prefix}Elimina", DELETE)
        return combo

    def _apply_all(self, source, targets):
        """The choice of a group to each of its elements (a deletion only to those that can be deleted)."""
        value = source.currentData()
        for combo in targets:
            index = combo.findData(value)
            combo.setCurrentIndex(index if index >= 0 else combo.findData(KEEP))

    @property
    def choices(self):
        """{uuid of an orphan: KEEP, DELETE or the uuid of the domain it passes to}."""
        return {uuid: combo.currentData() for uuid, combo in self.combos.items()}
