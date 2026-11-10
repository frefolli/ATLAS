"""«Notifiche»: the ADR proposed by other teams that concern a domain of the team of the user (created, changed,
deleted), every ADR for the members of the Design Authority, and the messages of their discussions (see
model.notifications), in tabs: all, for my team, as Design Authority, messages. A notification is opened (its
sheet), marked read, or unread again to look at it again; the alert at the opening of the project and after
«Ricevi» says how many are unread."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QPushButton, QTabBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from arcadia_tool.model import notifications as n
from arcadia_tool.model.discussions import when
from arcadia_tool.ui.model_tree import _dot
from arcadia_tool.ui.theme import MUTED, icon

# «Stato»: Nuova (never opened by the user of this PC), Letta (opened at least once); what happened (changed,
# deleted, a message) is in the description; the dot beside the ID and the bold: what is to look at (unread).
COLUMNS = ("ID", "Titolo", "Descrizione", "Tipo", "Stato", "Data e ora")
IDENT, TITLE, DETAIL, KIND, STATE, WHEN = range(len(COLUMNS))
COLOURS = {n.NEW: "#166534", n.READ: MUTED}
ALL = "all"


class NotificationsDialog(QDialog):
    """The notifications of the user. open_requested: the uuid of the ADR or CQ to show (the window closes)."""
    open_requested = Signal(str)

    def __init__(self, project, user, parent=None):
        super().__init__(parent)
        self.project, self.user = project, user
        self.setWindowTitle("Notifiche")
        self.resize(1100, 520)
        self.summary = QLabel(objectName="cardTitle")
        note = QLabel("«Stato»: Nuova se non l'hai ancora aperta (o l'hai rimessa come non letta), Letta se l'hai "
                      "aperta su questo PC; il pallino segna ciò che è da vedere (anche cambiato dopo la lettura). "
                      "Le ADR proposte da altri team che riguardano un dominio del tuo team come destinazione (create, "
                      "modificate o eliminate) e i messaggi delle loro discussioni. Una notifica si legge aprendola; "
                      "«Segna come non letta» la ripropone per riesaminarla. Lo stato di lettura resta su questo PC. "
                      "I membri della Design Authority ricevono tutte le ADR non aperte dalla DA, nella loro "
                      "scheda.", objectName="muted")
        # The tabs: why the notifications reach the user (the Design Authority only for its members).
        self.tabs = QTabBar()
        self.tabs.setDrawBase(False)
        self.scopes = [ALL, n.TEAM] + ([n.DA] if n._Who(project.model, user).is_da else []) + [n.MESSAGES]
        for scope in self.scopes:
            self.tabs.addTab(scope)
        self.tabs.currentChanged.connect(lambda _i: self.fill())
        note.setWordWrap(True)
        self.only_unread = QCheckBox("Solo non lette")
        self.only_unread.toggled.connect(lambda _on: self.fill())
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(COLUMNS)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        header = self.tree.header()
        for column, (mode, width) in enumerate(((QHeaderView.Interactive, 110), (QHeaderView.Interactive, 320),
                                                (QHeaderView.Stretch, 0), (QHeaderView.Interactive, 120),
                                                (QHeaderView.Interactive, 80), (QHeaderView.Interactive, 130))):
            header.setSectionResizeMode(column, mode)
            if width:
                header.resizeSection(column, width)
        self.tree.itemDoubleClicked.connect(lambda item, _c: self.open(item))
        self.tree.itemSelectionChanged.connect(self._update)
        self.open_button = QPushButton(icon("mdi6.open-in-new"), "Apri")
        self.open_button.clicked.connect(lambda _c=False: self.open())
        self.read_button = QPushButton(icon("mdi6.email-open-outline"), "Segna come letta")
        self.read_button.clicked.connect(lambda _c=False: self.mark(True))
        self.unread_button = QPushButton(icon("mdi6.email-outline"), "Segna come non letta")
        self.unread_button.clicked.connect(lambda _c=False: self.mark(False))
        self.all_button = QPushButton(icon("mdi6.email-multiple-outline"), "Segna tutte come lette")
        self.all_button.clicked.connect(lambda _c=False: self.mark_all())
        close = QPushButton("Chiudi")
        close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        for b in (self.open_button, self.read_button, self.unread_button, self.all_button):
            buttons.addWidget(b)
        buttons.addStretch()
        buttons.addWidget(close)
        top = QHBoxLayout()
        top.addWidget(self.summary)
        top.addStretch()
        top.addWidget(self.only_unread)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(note)
        layout.addWidget(self.tabs)
        layout.addWidget(self.tree, 1)
        layout.addLayout(buttons)
        self.fill()

    @property
    def scope(self):
        return self.scopes[max(self.tabs.currentIndex(), 0)]

    def fill(self):
        self.notifications = n.collect(self.project, self.user)
        unread = sum(1 for x in self.notifications if x.unread)
        for i, scope in enumerate(self.scopes):
            count = sum(1 for x in self.notifications if x.unread and (scope == ALL or scope in x.scopes))
            label = "Tutte" if scope == ALL else n.SCOPE_LABELS[scope]
            self.tabs.setTabText(i, f"{label} ({count})" if count else label)
        shown = [x for x in self.notifications if (x.unread or not self.only_unread.isChecked())
                 and (self.scope == ALL or self.scope in x.scopes)]
        self.summary.setText(f"{unread} {'notifica non letta' if unread == 1 else 'notifiche non lette'}" if unread
                             else "Nessuna notifica non letta")
        self.tree.clear()
        bold = QFont()
        bold.setBold(True)
        for x in shown:
            item = QTreeWidgetItem([x.ident, x.name or x.title, x.detail, x.kind, x.state, when(x.when)])
            item.setData(0, Qt.UserRole, x.key)
            item.setIcon(IDENT, _dot(x.unread))  # the blue dot: to look at
            item.setForeground(STATE, QBrush(QColor(COLOURS[x.state])))
            item.setToolTip(STATE, "Mai aperta da te su questo PC, o rimessa come non letta" if x.state == n.NEW
                            else "Aperta da te" + (": è cambiata dopo" if x.unread else ""))
            for column in range(len(COLUMNS)):
                if x.unread:
                    item.setFont(column, bold)
                elif column != STATE:
                    item.setForeground(column, QBrush(QColor(MUTED)))
            item.setToolTip(DETAIL, x.detail)
            item.setToolTip(TITLE, x.title)
            self.tree.addTopLevelItem(item)
        self.all_button.setEnabled(bool(unread))
        self._update()

    def selected(self):
        keys = {i.data(0, Qt.UserRole) for i in self.tree.selectedItems()}
        return [x for x in self.notifications if x.key in keys]

    def _update(self):
        chosen = self.selected()
        self.open_button.setEnabled(len(chosen) == 1 and chosen[0].event != n.DELETED)
        self.read_button.setEnabled(any(x.unread or not x.opened for x in chosen))
        self.unread_button.setEnabled(any(x.opened for x in chosen))  # «Letta» → «Nuova»

    def mark(self, read, chosen=None):
        for x in chosen or self.selected():
            if read and (x.unread or not x.opened):
                n.mark_read(self.project, self.user, x)
            elif not read and x.opened:
                n.mark_unread(self.project, self.user, x)
        self.fill()

    def mark_all(self):
        self.mark(True, [x for x in self.notifications if x.unread])

    def open(self, item=None):
        chosen = [x for x in self.notifications if item is not None and x.key == item.data(0, Qt.UserRole)] \
            if item is not None else self.selected()
        if len(chosen) != 1 or chosen[0].event == n.DELETED:
            if chosen and chosen[0].event == n.DELETED:  # nothing to open: read
                self.mark(True, chosen)
            return
        if chosen[0].unread:
            n.mark_read(self.project, self.user, chosen[0])
        self.open_requested.emit(chosen[0].subject)
        self.accept()


def alert(parent, project, user, open_panel, after=""):
    """The explicit alert of the notifications unread (not modal: the work goes on). after: what has just happened
    («Versioni ricevute»). Returns the box, or None if nothing is unread."""
    unread = [x for x in n.collect(project, user) if x.unread]
    if not unread:
        return None
    team = sum(1 for x in unread if n.TEAM in x.scopes)
    da = sum(1 for x in unread if n.DA in x.scopes and n.TEAM not in x.scopes)
    messages = sum(1 for x in unread if n.MESSAGES in x.scopes)
    parts = [f"{team} {'ADR che riguarda' if team == 1 else 'ADR che riguardano'} i domini del tuo team"
             if team else "", f"{da} ADR da esaminare come Design Authority" if da else "",
             f"{messages} {'messaggio nuovo' if messages == 1 else 'messaggi nuovi'} nelle discussioni"
             if messages else ""]
    parts = [p for p in parts if p]
    listed = ", ".join(parts[:-1]) + " e " + parts[-1] if len(parts) > 1 else parts[0]
    box = QMessageBox(QMessageBox.Question, "Notifiche", (f"{after}. " if after else "") + "Hai " + listed +
                      " da leggere.", parent=parent)
    box.setInformativeText("Vuoi aprire le Notifiche?")
    opened = box.addButton("Apri le Notifiche", QMessageBox.AcceptRole)
    box.addButton("Più tardi", QMessageBox.RejectRole)
    box.setWindowModality(Qt.NonModal)
    box.buttonClicked.connect(lambda button: open_panel() if button is opened else None)
    box.show()
    return box
