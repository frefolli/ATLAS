"""The catalogue of the clauses declared by the teams as shared among domains, or as mapped to no domain, in a tab:
one row per clause and ADR (also closed or rejected), the ADR opened from its row."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from arcadia_tool.model.adr import clause_decisions, outcome, principal_of
from arcadia_tool.model.schema import ADR_SHARED, ADR_UNMAPPED
from arcadia_tool.ui.theme import icon, status_colors

TITLES = {ADR_SHARED: "Clausole condivise", ADR_UNMAPPED: "Clausole non mappate"}
NOTES = {ADR_SHARED: "Le clausole che i team hanno indicato come condivise tra più domini, con l'ADR che lo propone o "
                     "lo decide. Doppio clic su una riga per aprire l'ADR.",
         ADR_UNMAPPED: "Le clausole che i team hanno indicato come non assegnate a nessun dominio, con l'ADR che lo "
                       "propone o lo decide. Doppio clic su una riga per aprire l'ADR."}


def columns(adr_type):
    extra = ("Dominio principale", "Condivisa con") if adr_type == ADR_SHARED else ("Motivo",)
    return ("Clausola", "Testo", *extra, "ADR", "Esito", "Stato ADR")


class ClauseCatalog(QWidget):
    """open_requested: the uuid of the ADR of a row, to open in its sheet; new_requested: «Nuova…», a clause to declare
    (shared, or mapped to no domain) with its ADR, as from the menu of the list in the tree."""
    open_requested = Signal(str)
    new_requested = Signal()

    def __init__(self, project, adr_type, parent=None):
        super().__init__(parent)
        self.project, self.adr_type = project, adr_type
        self.title = TITLES[adr_type]
        self.search = QLineEdit(placeholderText="Cerca per clausola, testo, dominio o ADR", objectName="search")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self._filter())
        names = columns(adr_type)
        self.table = QTableWidget(0, len(names))
        self.table.setHorizontalHeaderLabels(names)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        for c, name in enumerate(names):
            header.setSectionResizeMode(c, QHeaderView.Stretch if name == "Testo" else QHeaderView.Interactive)
        header.setMinimumSectionSize(60)
        self.table.doubleClicked.connect(lambda _i: self.open_adr())
        self.table.itemSelectionChanged.connect(self._update)
        self.open_button = QPushButton(icon("mdi6.open-in-new"), "Apri l'ADR")
        self.open_button.clicked.connect(lambda _=False: self.open_adr())
        self.new_button = QPushButton(icon("mdi6.plus", "white"), "Nuova…")
        self.new_button.setProperty("primary", True)
        self.new_button.setToolTip("Scegli le clausole da condividere: ATLAS crea l'ADR già compilata"
                                   if adr_type == ADR_SHARED else
                                   "Scegli le clausole da non mappare: ATLAS crea l'ADR già compilata")
        self.new_button.clicked.connect(lambda _=False: self.new_requested.emit())
        self.count = QLabel(objectName="cardTitle")
        top = QHBoxLayout()
        top.addWidget(self.count)
        top.addStretch()
        top.addWidget(self.open_button)
        top.addWidget(self.new_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.addLayout(top)
        layout.addWidget(QLabel(f"{NOTES[adr_type]} Specifica: {project.baseline or 'SRS'}.", objectName="muted",
                                wordWrap=True))
        layout.addWidget(self.search)
        layout.addWidget(self.table, 1)
        self.reload()

    def reload(self):
        """The rows as the ADR are now (an ADR changed, created or removed)."""
        model = self.project.model

        def short(uuid):
            e = model.get(uuid) if uuid else None
            return (e.get("id") or model.label(e)) if e is not None else ""

        rows = clause_decisions(model, self.adr_type)
        self.count.setText(f"{self.title}: {len({item.uuid for item, _a in rows})} clausole, "
                           f"{len({a.uuid for _i, a in rows})} ADR")
        self.table.setRowCount(len(rows))
        for r, (item, adr) in enumerate(rows):
            text = " ".join((item.get("text") or item.get("title") or "").split())
            if self.adr_type == ADR_SHARED:
                extra = (short(principal_of(model, item)), ", ".join(short(d) for d in adr.get("shared_with") or []))
            else:
                extra = (adr.get("unmapped_reason") or "",)
            values = (item.get("id") or "", text, *extra, adr.get("id") or "ADR", outcome(adr), adr.get("status") or "")
            for c, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.UserRole, adr.uuid)
                cell.setToolTip(value)  # the whole value, also where the column cuts it
                self.table.setItem(r, c, cell)
            for c in (len(values) - 2, len(values) - 1):  # the outcome and the status, coloured as in the sheets
                fg, _bg = status_colors(values[c])
                if fg:
                    self.table.item(r, c).setForeground(QBrush(QColor(fg)))
        self._fit_columns()
        self._filter()
        self._update()

    def _fit_columns(self):
        """Each column but «Testo» as wide as its heading and its values (the heading always readable), within a
        limit: the text takes the rest."""
        header = self.table.horizontalHeader()
        metrics = header.fontMetrics()
        for c in range(self.table.columnCount()):
            if header.sectionResizeMode(c) == QHeaderView.Stretch:
                continue
            self.table.resizeColumnToContents(c)
            label = self.table.horizontalHeaderItem(c).text()
            heading = metrics.horizontalAdvance(label) + 36  # its margins and the sort indicator
            header.resizeSection(c, min(max(header.sectionSize(c), heading), max(heading, 260)))

    def _filter(self):
        words = self.search.text().lower().split()
        for r in range(self.table.rowCount()):
            text = " ".join(self.table.item(r, c).text().lower() for c in range(self.table.columnCount()))
            self.table.setRowHidden(r, not all(w in text for w in words))

    def selected_adr(self):
        rows = {i.row() for i in self.table.selectedIndexes()}
        return self.table.item(min(rows), 0).data(Qt.UserRole) if rows else None

    def _update(self):
        self.open_button.setEnabled(self.selected_adr() is not None)

    def open_adr(self):
        uuid = self.selected_adr()
        if uuid:
            self.open_requested.emit(uuid)
