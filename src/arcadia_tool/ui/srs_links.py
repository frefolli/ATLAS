"""«Collega…» of a clause in the catalogue of the SRS items: its links to other SRS items (see model.srs_links), each
with its type («Richiama», «Include», «Dipende da»); new ones chosen in the traceability window; those to it from
the others shown below, read-only."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget,
                               QPushButton, QRadioButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from arcadia_tool.model.srs_links import INVERSE, LINK_TYPES, incoming, links_of
from arcadia_tool.ui.element_editor import card
from arcadia_tool.ui.theme import icon

# What each type means, read «this clause → the other item»: (meaning, example, what it changes); the example: a
# clause of the SUBSET-026 (its number, its whole text, the item it links).
MEANINGS = {
    "Richiama": ("La clausola cita l'altra voce per rimandare il lettore lì, ma il suo obbligo è un altro e si traccia "
                 "da sola.",
                 ("3.4.4.1.2", "A balise group is linked when its linking information (see section 3.4.4.2) is "
                  "known in advance.", "3.4.4.2"),
                 "Solo informativo. Se l'altra voce è di un altro dominio, le verifiche lo segnalano: può servire uno "
                 "scambio funzionale o una condivisione con quel dominio."),
    "Include": ("Il contenuto dell'altra voce vale anche qui: è come se il suo testo fosse scritto dentro questa "
                "clausola.",
                ("3.8.4.4.3", "If the train comes to a standstill after the Overlap timer has been started, the "
                 "on-board shall consider that the Overlap timer value became greater than its time-out value and "
                 "shall apply 3.8.4.4.2.", "3.8.4.4.2"),
                "Per la parte inclusa questa clausola è coperta dalla tracciatura dell'altra (esito SA-3 «Coperta "
                "dalla clausola inclusa», report di copertura)."),
    "Dipende da": ("La clausola si può realizzare solo se è realizzato ciò che l'altra voce stabilisce o fa (un dato, "
                   "uno stato, una funzione).",
                   ("3.4.2.3.3.8", "A co-ordinate system assignment received from trackside shall be rejected by "
                    "the ERTMS/ETCS on-board equipment if the referred LRBG is memorised (see 3.6.2.2.2c) to have "
                    "been reported more than once and with different “previous LRBGs”.", "3.6.2.2.2"),
                   "Solo informativo. Se l'altra voce è di un altro dominio, le verifiche lo segnalano: può servire "
                   "uno scambio funzionale o una condivisione con quel dominio."),
}
PHRASES = {"Richiama": "richiama l'altra voce", "Include": "include l'altra voce", "Dipende da": "dipende dall'altra voce"}
VERBS = {"Richiama": "richiama", "Include": "include", "Dipende da": "dipende da"}


def example_text(link_type, html=True):
    """The example of a type: the whole text of the clause, then the link it gives."""
    clause, text, target = MEANINGS[link_type][1]
    if html:
        from html import escape
        return (f"Es.: <b>{clause}</b> «<i>{escape(text)}</i>»<br>→ {clause} <b>{VERBS[link_type]}</b> {target}")
    return f"Es.: {clause} «{text}» → {clause} {VERBS[link_type]} {target}"


TYPE_TIPS = {t: f"{m[0]}\n{example_text(t, html=False)}\n{m[2]}" for t, m in MEANINGS.items()}


class LinkTypeDialog(QDialog):
    """The type of the new links, chosen knowing what it means: each type with its meaning, an example and what it
    changes."""

    def __init__(self, item_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tipo di collegamento")
        self.resize(860, 640)
        layout = QVBoxLayout(self)
        title = QLabel(f"Che relazione ha la clausola {item_id} con le voci da collegare?", objectName="cardTitle")
        title.setWordWrap(True)
        layout.addWidget(title)
        self.group = QButtonGroup(self)
        self.buttons = {}
        for link_type, (meaning, example, effect) in MEANINGS.items():
            button = QRadioButton(f"{item_id} {PHRASES[link_type]}")
            button.setStyleSheet("QRadioButton { font-weight: 600; }")
            self.group.addButton(button)
            self.buttons[link_type] = button
            layout.addWidget(button)
            text = QLabel(f"{meaning}<br>{example_text(link_type)}<br>{effect}", objectName="muted")
            text.setTextFormat(Qt.RichText)
            text.setWordWrap(True)
            text.setContentsMargins(24, 0, 0, 8)
            layout.addWidget(text)
        layout.addStretch()
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton(icon("mdi6.arrow-right", "white"), "Scegli le voci…")
        self.ok.setProperty("primary", True)
        self.ok.setEnabled(False)  # a type must be chosen: none is proposed, not to take one without reading
        self.ok.clicked.connect(self.accept)
        self.group.buttonToggled.connect(lambda *_: self.ok.setEnabled(self.chosen is not None))
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.ok)
        layout.addLayout(buttons)

    @property
    def chosen(self):
        return next((t for t, b in self.buttons.items() if b.isChecked()), None)


def edit_links(project, item, parent=None):
    """«Collega…» of an SRS item (from its row in the catalogue, or from the model tree): its links changed in
    LinksDialog. Returns the elements changed (to show and save), or None if nothing changed."""
    from arcadia_tool.model.srs_links import link_rows

    dialog = LinksDialog(project, item, parent)
    if not dialog.exec() or dialog.links == links_of(item):
        return None
    previous = item.copy()
    item.set("links", link_rows(dialog.links))
    return [item, *(project.update(item, previous) or [])]


def short(model, item):
    text = " ".join((item.get("title") or item.get("text") or "").split())
    return f"{item.get('id') or ''}  {text[:90]}{'…' if len(text) > 90 else ''}".strip()


class LinksDialog(QDialog):
    def __init__(self, project, item, parent=None):
        super().__init__(parent)
        self.project, self.item = project, item
        model = project.model
        self.setWindowTitle(f"Collegamenti di {item.get('id') or ''}")
        self.resize(960, 620)
        header, header_layout = card()
        header_layout.addWidget(QLabel(f"Collegamenti di {item.get('id') or ''}", objectName="elementTitle"))
        ident = item.get("id") or "la clausola"
        hint = QLabel(f"Le altre voci SRS che {ident} richiama, include o da cui dipende; si legge dalla clausola verso "
                      f"l'altra voce («{ident} include 3.8.4.4.2»). Il significato di ogni tipo è spiegato quando lo "
                      "scegli con «Aggiungi collegamento…»; sul tipo di una riga, col mouse.", objectName="muted")
        hint.setAccessibleName("linkLegend")
        hint.setWordWrap(True)
        header_layout.addWidget(hint)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Tipo", "Voce SRS", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.add_button = QPushButton(icon("mdi6.link-variant-plus"), "Aggiungi collegamento…")
        self.add_button.setToolTip("Scegli prima il tipo di relazione, poi le voci da collegare")
        self.add_button.clicked.connect(lambda _=False: self.add())
        self.incoming = QListWidget()
        self.incoming.setMaximumHeight(110)
        for link_type, source in incoming(model, item.uuid):
            self.incoming.addItem(f"{INVERSE[link_type]} {short(model, source)}")
        if not self.incoming.count():
            self.incoming.addItem("Nessuna altra voce la collega")
            self.incoming.item(0).setFlags(Qt.NoItemFlags)
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        ok = QPushButton(icon("mdi6.check", "white"), "Applica")
        ok.setProperty("primary", True)
        ok.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(self.add_button)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(QLabel("Questa clausola:"))
        layout.addWidget(self.table, 1)
        layout.addWidget(QLabel("Le altre voci che la collegano:"))
        layout.addWidget(self.incoming)
        layout.addLayout(buttons)
        for link_type, target in links_of(item):
            self._row(link_type, target)

    def _row(self, link_type, target):
        model = self.project.model
        element = model.get(target)
        r = self.table.rowCount()
        self.table.insertRow(r)
        kind = QComboBox()
        for t in LINK_TYPES:
            kind.addItem(t)
            kind.setItemData(kind.count() - 1, TYPE_TIPS[t], Qt.ToolTipRole)
        kind.setCurrentText(link_type)
        self.table.setCellWidget(r, 0, kind)
        cell = QTableWidgetItem(short(model, element) if element is not None else "(voce inesistente)")
        cell.setData(Qt.UserRole, target)
        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(r, 1, cell)
        remove = QPushButton(icon("mdi6.close"), "")
        remove.setToolTip("Togli il collegamento")
        remove.clicked.connect(lambda _=False, c=cell: self.table.removeRow(self.table.row(c)))
        self.table.setCellWidget(r, 2, remove)

    def add(self, link_type=None):
        """New links: their type chosen first, knowing what it means (LinkTypeDialog), then the SRS items ticked in
        the traceability window (not the clause itself)."""
        from arcadia_tool.ui.srs_trace import pick_srs_items

        if link_type is None:
            dialog = LinkTypeDialog(self.item.get("id") or "la clausola", self)
            if not dialog.exec() or dialog.chosen is None:
                return
            link_type = dialog.chosen
        chosen = pick_srs_items(self.project, f"Collegamenti di {self.item.get('id') or ''}",
                                f"le voci che la clausola «{link_type.lower()}»", [], self)
        for target in chosen or []:
            if target != self.item.uuid and (link_type, target) not in self.links:
                self._row(link_type, target)

    @property
    def links(self):
        """[(type, target uuid)] as in the table."""
        return [(self.table.cellWidget(r, 0).currentText(), self.table.item(r, 1).data(Qt.UserRole))
                for r in range(self.table.rowCount())]
