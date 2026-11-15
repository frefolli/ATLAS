"""«Modifiche locali» (Ctrl+Alt+Z): the local changes not yet published, in the order they were made (see
storage.journal). The last one can be discarded, and the last discarded one restored, one at a time."""
from datetime import datetime
from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QSplitter,
                               QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from arcadia_tool.diff.semantic import ADDED, MODIFIED, REMOVED, ElementChange, ModelDiff, _diff_element
from arcadia_tool.model.element import Model
from arcadia_tool.model.serialization import loads
from arcadia_tool.storage.journal import JournalError
from arcadia_tool.ui.busy import run_busy
from arcadia_tool.ui.diff_view import CSS, change_html
from arcadia_tool.ui.element_editor import card
from arcadia_tool.ui.theme import MUTED, icon

ENTRY_ROLE = Qt.UserRole + 1
SHORTCUT = "Ctrl+Alt+Z"


def _time(text):
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        return text
    return f"{when:%H:%M:%S}" if when.date() == datetime.now().date() else f"{when:%d/%m/%Y %H:%M}"


class _Overlay(Model):
    """The model with some elements as an entry has them (before or after): the other references keep their labels."""

    def __init__(self, base, texts):
        super().__init__()
        self.elements = dict(base.elements)
        for uuid, text in texts.items():
            if text is None:
                self.elements.pop(uuid, None)
            else:
                self.elements[uuid] = loads(text)


def entry_diff(model, entry):
    """The changes of an entry as in the comparison of versions (see diff_view.change_html)."""
    before = _Overlay(model, {c.uuid: c.before for c in entry.changes})
    after = _Overlay(model, {c.uuid: c.after for c in entry.changes})
    changes = []
    for c in entry.changes:
        b, a = before.get(c.uuid), after.get(c.uuid)
        if b is None:
            change = ElementChange(c.uuid, a.kind, ADDED, None, a)
        elif a is None:
            change = ElementChange(c.uuid, b.kind, REMOVED, b, None)
        else:
            change = ElementChange(c.uuid, a.kind, MODIFIED, b, a, _diff_element(b, a))
        change.label_before = before.label(b) if b is not None else ""
        change.label_after = after.label(a) if a is not None else ""
        changes.append(change)
    return ModelDiff(before, after, changes)


LINKED_BG = "#FEF3C7"  # the entries that go with the one chosen


class LocalChangesDialog(QDialog):
    """changed(uuids): elements put back or restored, for the main window to show them."""
    changed = Signal(set)

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.journal = project.journal
        self.setWindowTitle("Modifiche locali")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        self.resize(1180, 720)
        run_busy(parent, "Lettura delle modifiche locali…", lambda _report: self.journal.add_baseline())
        intro = QLabel("Le modifiche non ancora pubblicate, dalla prima all'ultima. Scarta l'ultima, oppure scegline "
                       "una precedente: si scartano con lei le modifiche successive collegate (sugli stessi elementi, "
                       "o su elementi che lei crea o elimina), evidenziate. Una modifica scartata si ripristina con le "
                       "modifiche scartate precedenti che le servono.")
        intro.setWordWrap(True)
        self.list = QTreeWidget()
        self.list.setHeaderLabels(["Ora", "Modifica", "Elementi"])
        self.list.setRootIsDecorated(False)
        header = self.list.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        self.list.currentItemChanged.connect(lambda _c, _p: self._chosen())
        self.detail = QTextBrowser()
        splitter = QSplitter()
        splitter.addWidget(self.list)
        splitter.addWidget(self.detail)
        splitter.setSizes([620, 520])
        changes, changes_layout = card("Modifiche locali, in ordine cronologico")
        changes_layout.addWidget(splitter, 1)
        self.note = QLabel(objectName="muted")
        self.note.setWordWrap(True)
        changes_layout.addWidget(self.note)
        self.state = QLabel(objectName="muted")
        self.state.setWordWrap(True)
        changes_layout.addWidget(self.state)

        self.undo_button = QPushButton(icon("mdi6.undo", "#B42318"), "Scarta l'ultima modifica")
        self.undo_button.clicked.connect(lambda: self._apply(True, None))
        self.redo_button = QPushButton(icon("mdi6.redo"), "Ripristina l'ultima scartata")
        self.redo_button.clicked.connect(lambda: self._apply(False, None))
        self.selected_button = QPushButton()  # the one chosen in the list: discarded, or restored
        self.selected_button.clicked.connect(self._apply_selected)
        close = QPushButton("Chiudi")
        close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(self.undo_button)
        buttons.addWidget(self.redo_button)
        buttons.addSpacing(16)
        buttons.addWidget(self.selected_button)
        buttons.addStretch()
        buttons.addWidget(close)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(intro)
        layout.addWidget(changes, 1)
        layout.addLayout(buttons)
        self._fill()
        close.setFocus()

    def _items(self):
        return [self.list.topLevelItem(i) for i in range(self.list.topLevelItemCount())]

    def _fill(self, current=None):
        self.list.blockSignals(True)
        self.list.clear()
        entries = self.journal.entries
        done, undone = self.journal.last_done(), self.journal.last_undone()
        struck = QFont()
        struck.setStrikeOut(True)
        chosen = None
        for entry in entries:
            item = QTreeWidgetItem(self.list, [_time(entry.time), entry.label, str(len(entry.changes))])
            item.setData(0, ENTRY_ROLE, entry)
            item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
            if entry.undone:
                item.setIcon(1, icon("mdi6.undo", MUTED))
                for column in range(3):
                    item.setForeground(column, QBrush(QColor(MUTED)))
                item.setFont(1, struck)
                item.setToolTip(1, "Scartata: si può ripristinare")
            else:
                item.setIcon(1, icon("mdi6.circle-medium", "#3D4B5C"))
                item.setToolTip(1, entry.label)
            if entry.baseline:
                item.setText(0, "—")
                item.setToolTip(1, "Le modifiche non pubblicate fatte prima di quelle elencate dopo (anche in sessioni "
                                   "precedenti), tutte insieme")
            if entry is current or (current is None and entry is done):
                chosen = item
        self.list.blockSignals(False)
        if chosen is None and entries:
            chosen = self._items()[-1]
        self.undo_button.setEnabled(done is not None)
        self.undo_button.setToolTip(f"Scarta «{done.label}»: i suoi elementi tornano come prima" if done else
                                    "Nessuna modifica da scartare")
        self.redo_button.setEnabled(undone is not None)
        self.redo_button.setToolTip(f"Ripristina «{undone.label}»" if undone else "Nessuna modifica scartata")
        active = sum(1 for e in entries if not e.undone)
        self.state.setText(f"{active} {'modifica' if active == 1 else 'modifiche'} in vigore"
                           + (f" · {len(entries) - active} scartate, da ripristinare" if len(entries) > active else ""))
        if chosen is not None:
            self.list.setCurrentItem(chosen)
            self.list.scrollToItem(chosen)
        else:
            self.detail.setHtml(f"<style>{CSS}</style><p class='kind'>Nessuna modifica locale: il modello è come "
                                "l'ultima versione pubblicata.</p>")
        self._chosen()

    def selected(self):
        item = self.list.currentItem()
        return item.data(0, ENTRY_ROLE) if item is not None else None

    def group(self):
        """The entries that go with the one chosen: discarded with it, or restored with it."""
        entry = self.selected()
        if entry is None:
            return []
        return self.journal.to_redo(entry) if entry.undone else self.journal.to_undo(entry)

    def _chosen(self):
        """The entry chosen: its detail, the entries linked to it highlighted, its button."""
        entry = self.selected()
        others = [e for e in self.group() if e is not entry]
        for item in self._items():
            linked_ = any(item.data(0, ENTRY_ROLE) is e for e in others)
            for column in range(3):
                item.setBackground(column, QBrush(QColor(LINKED_BG)) if linked_ else QBrush())
        self.selected_button.setVisible(entry is not None)
        if entry is None:
            self.note.setVisible(False)
            return
        n = len(others)
        verb = "Ripristina" if entry.undone else "Scarta"
        self.selected_button.setIcon(icon("mdi6.redo") if entry.undone else icon("mdi6.undo", "#B42318"))
        self.selected_button.setText(f"{verb} la selezionata" + (f" e {n} collegat{'a' if n == 1 else 'e'}"
                                                                   if n else ""))
        if others:
            names = ", ".join(f"«{e.label}»" for e in others)
            self.note.setText(("Si ripristinano anche, perché le servono: " if entry.undone else
                               "Si scartano anche, perché collegate: ") + names)
        self.note.setVisible(bool(others))
        diff = entry_diff(self.project.model, entry)
        state = "<p class='kind'>Scartata: i suoi elementi sono come prima.</p>" if entry.undone else ""
        parts = [f"<style>{CSS}</style><h2>{escape(entry.label)}</h2>{state}"]
        for change in diff.changes:
            parts.append(change_html(diff, change).replace(f"<style>{CSS}</style>", ""))
        self.detail.setHtml("".join(parts))

    def _apply_selected(self):
        entry = self.selected()
        if entry is not None:
            self._apply(not entry.undone, entry)

    def _apply(self, undo, entry):
        try:
            group = self.journal.undo(entry) if undo else self.journal.redo(entry)
        except JournalError as error:
            QMessageBox.warning(self, "Modifiche locali", str(error))
            return
        if not group:
            return
        self._fill(entry or group[0])
        self.changed.emit({c.uuid for e in group for c in e.changes})

    def undo(self):
        self._apply(True, None)

    def redo(self):
        self._apply(False, None)
