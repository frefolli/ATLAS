"""«Discussione» in the sheet of an ADR or of a CQ: the messages of the members of the teams, in a row, and the box
to write one (with the files attached). A message is saved at once, on its own (the sheet does not need to be in
edit mode, and its changes in progress are not saved with it): it reaches the others when the project is published
and sent, as any other change (see model.discussions)."""
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
                               QPlainTextEdit, QPushButton, QToolButton, QVBoxLayout, QWidget)

from arcadia_tool.documents.values import plain
from arcadia_tool.model import discussions as d
from arcadia_tool.model.teams import memberships
from arcadia_tool.ui.busy import save_project
from arcadia_tool.ui.element_editor import card
from arcadia_tool.ui.theme import ACCENT, MUTED, icon

QUOTE_LENGTH = 140


def _short(text):
    """The start of a message quoted, as plain text (without the marks of Markdown)."""
    text = " ".join(plain(text).replace("`", "").split())
    return text if len(text) <= QUOTE_LENGTH else text[:QUOTE_LENGTH].rstrip() + "…"


class DiscussionCard(QWidget):
    """The discussion of `subject` for `user` (the account logged in). changed: a message written, changed,
    deleted or hidden, and saved."""
    changed = Signal()

    def __init__(self, project, subject, user, parent=None):
        super().__init__(parent)
        self.project, self.subject, self.user = project, subject, user
        self.reply_to = None
        self.files = []  # [(name, bytes)] attached to the message being written
        self.setProperty("keepEnabled", True)  # also in a read-only sheet: writing here does not edit the sheet
        model = project.model
        self.new = {m.uuid for m in d.unread(model, subject, user, d.seen(project, subject))}
        d.mark_read(project, subject)
        messages = d.messages_of(model, subject)
        frame, self.body = card(f"Discussione · {len(messages)} {'messaggio' if len(messages) == 1 else 'messaggi'}"
                                + (f" · {len(self.new)} {'nuovo' if len(self.new) == 1 else 'nuovi'}"
                                   if self.new else ""))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(frame)
        self.closed = d.closed(model, subject)
        published = project.repository.head_paths()
        self.published = {m.uuid for m in messages
                          if project._relative(project.element_file(m)) in published}
        if not messages:
            self.body.addWidget(QLabel("Nessun messaggio: avvia la discussione scrivendo qui sotto.",
                                       objectName="muted"))
        for m in messages:
            self.body.addWidget(self._message(m))
        denied = d.write_denied(model, subject, user)
        if denied:
            note = QLabel(denied, objectName="muted")
            note.setWordWrap(True)
            self.body.addWidget(note)
        else:
            self.body.addWidget(self._composer())

    # --- the messages ---------------------------------------------------------------------------------------------

    def _message(self, m):
        model = self.project.model
        box = QFrame(objectName="message")
        box.setStyleSheet(f"QFrame#message {{ border-left: 3px solid {ACCENT if m.uuid in self.new else '#C9D1DC'};"
                          " padding-left: 8px; }")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(3)
        team = model.get(m.get("team")) if m.get("team") else None
        head = " · ".join(t for t in (m.get("author") or "Autore sconosciuto",
                                      team.get("id") or team.get("name") if team else "",
                                      d.when(m.get("posted"))) if t)
        if m.get("edited") and not m.get("deleted"):
            head += f" · modificato il {d.when(m.get('edited'))}"
        if m.uuid in self.new:
            head += " · nuovo"
        if m.uuid not in self.published:
            head += " · non ancora pubblicato"
        title = QLabel(head, objectName="formLabel")
        title.setToolTip(team.get("name") if team else "")
        layout.addWidget(title)
        answered = model.get(m.get("reply_to")) if m.get("reply_to") else None
        if answered is not None:
            quote = QLabel(f"In risposta a {answered.get('author') or 'un messaggio'}: «"
                           f"{_short('messaggio eliminato' if answered.get('deleted') else answered.get('text'))}»",
                           objectName="muted")
            quote.setWordWrap(True)
            layout.addWidget(quote)
        hidden = m.get("hidden_by_da")
        da = d.may_hide(model, self.user)
        if m.get("deleted"):
            text = QLabel("Messaggio eliminato dall'autore.", objectName="muted")
        elif hidden and not da:
            text = QLabel("Messaggio nascosto dalla Design Authority.", objectName="muted")
        else:
            text = QLabel(m.get("text") or "")
            text.setTextFormat(Qt.MarkdownText)
            if hidden:
                text.setStyleSheet(f"color: {MUTED};")
                text.setToolTip("Nascosto dalla Design Authority: gli altri non lo vedono")
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        layout.addWidget(text)
        if not m.get("deleted") and not (hidden and not da):
            for path in m.get("attachments") or []:
                layout.addWidget(self._attachment(path))
        actions = QHBoxLayout()
        actions.setSpacing(4)
        if not self.closed and not m.get("deleted") and not d.write_denied(model, self.subject, self.user):
            actions.addWidget(self._action("mdi6.reply-outline", "Rispondi", lambda _c=False, m=m: self.answer(m)))
        if d.may_change(model, m, self.user):
            actions.addWidget(self._action("mdi6.pencil-outline", "Modifica", lambda _c=False, m=m: self.change(m)))
            actions.addWidget(self._action("mdi6.trash-can-outline", "Elimina", lambda _c=False, m=m: self.remove(m)))
        if da and not m.get("deleted"):
            label = "Mostra" if hidden else "Nascondi"
            actions.addWidget(self._action("mdi6.eye-outline" if hidden else "mdi6.eye-off-outline", label,
                                           lambda _c=False, m=m: self.hide(m)))
        actions.addStretch()
        layout.addLayout(actions)
        return box

    @staticmethod
    def _action(name, text, slot):
        button = QToolButton(autoRaise=True)
        button.setIcon(icon(name))
        button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        button.clicked.connect(slot)
        return button

    def _attachment(self, path):
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        name = d.attachment_name(path)
        data = self.project.asset_data(path)
        size = f" ({len(data) / 1024:.0f} KB)" if data is not None else " (non disponibile su questo PC)"
        opened = QToolButton(autoRaise=True)
        opened.setIcon(icon("mdi6.paperclip"))
        opened.setText(name + size)
        opened.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        opened.setToolTip("Apri l'allegato")
        opened.setEnabled(data is not None)
        opened.clicked.connect(lambda _c=False: self.open_attachment(path))
        saved = QToolButton(autoRaise=True)
        saved.setIcon(icon("mdi6.content-save-outline"))
        saved.setToolTip("Salva l'allegato con nome…")
        saved.setEnabled(data is not None)
        saved.clicked.connect(lambda _c=False: self.save_attachment(path))
        line.addWidget(opened)
        line.addWidget(saved)
        line.addStretch()
        return row

    def open_attachment(self, path):
        """A copy of the file in the temporary folder, opened with its program."""
        data = self.project.asset_data(path)
        if data is None:
            return None
        target = Path(tempfile.gettempdir()) / "ATLAS-allegati" / Path(path).parent.name / d.attachment_name(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        return target

    def save_attachment(self, path, target=None):
        data = self.project.asset_data(path)
        if data is None:
            return None
        if target is None:
            target, _ = QFileDialog.getSaveFileName(self, "Salva l'allegato", d.attachment_name(path))
            if not target:
                return None
        Path(target).write_bytes(data)
        return target

    # --- writing --------------------------------------------------------------------------------------------------

    def _composer(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 8, 0, 0)
        self.replying = QLabel(objectName="muted")
        self.replying.setWordWrap(True)
        self.cancel_reply = QToolButton(autoRaise=True)
        self.cancel_reply.setIcon(icon("mdi6.close"))
        self.cancel_reply.setToolTip("Non rispondere a questo messaggio")
        self.cancel_reply.clicked.connect(lambda _c=False: self.answer(None))
        reply_row = QHBoxLayout()
        reply_row.addWidget(self.replying, 1)
        reply_row.addWidget(self.cancel_reply)
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Scrivi un messaggio… (si può usare la formattazione Markdown: **grassetto**, "
                                     "elenchi con «-»)")
        self.text.setFixedHeight(90)
        self.text.textChanged.connect(self._update)
        self.team = QComboBox()
        for t, _row in memberships(self.project.model, self.user):
            self.team.addItem(self.project.model.label(t), t.uuid)
        self.team.setToolTip("Il team per cui scrivi")
        self.team.setVisible(self.team.count() > 1)
        attach = QPushButton(icon("mdi6.paperclip"), "Allega file…")
        attach.clicked.connect(lambda _c=False: self.attach())
        self.attached = QLabel(objectName="muted")
        self.attached.setWordWrap(True)
        self.clear_files = QToolButton(autoRaise=True)
        self.clear_files.setIcon(icon("mdi6.close"))
        self.clear_files.setToolTip("Togli gli allegati")
        self.clear_files.clicked.connect(lambda _c=False: self._set_files([]))
        self.send_button = QPushButton(icon("mdi6.send", "white"), "Invia")
        self.send_button.setProperty("primary", True)
        self.send_button.clicked.connect(lambda _c=False: self.send())
        buttons = QHBoxLayout()
        buttons.addWidget(attach)
        buttons.addWidget(self.attached, 1)
        buttons.addWidget(self.clear_files)
        buttons.addWidget(self.team)
        buttons.addWidget(self.send_button)
        layout.addLayout(reply_row)
        layout.addWidget(self.text)
        layout.addLayout(buttons)
        note = QLabel("Il messaggio si salva subito nel progetto e arriva ai colleghi quando pubblichi e invii le "
                      "versioni.", objectName="muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.answer(None)
        self._set_files([])
        return box

    def _update(self):
        if hasattr(self, "send_button"):
            self.send_button.setEnabled(bool(self.text.toPlainText().strip() or self.files))

    def answer(self, message):
        self.reply_to = message
        if not hasattr(self, "replying"):
            return
        self.replying.setText(f"In risposta a {message.get('author') or 'un messaggio'}: «"
                              f"{_short(message.get('text'))}»" if message is not None else "")
        self.replying.setVisible(message is not None)
        self.cancel_reply.setVisible(message is not None)
        if message is not None:
            self.text.setFocus()

    def attach(self, paths=None):
        if paths is None:
            paths, _ = QFileDialog.getOpenFileNames(self, "Allega file al messaggio")
        files = list(self.files)
        for path in paths:
            path = Path(path)
            size = path.stat().st_size
            if size > d.MAX_ATTACHMENT:
                QMessageBox.warning(self, "Allega file", f"«{path.name}» è di {size / 1024 / 1024:.1f} MB: gli "
                                    f"allegati arrivano al massimo a {d.MAX_ATTACHMENT // 1024 // 1024} MB, perché "
                                    "restano in ogni copia del repository.")
                continue
            files.append((path.name, path.read_bytes()))
        self._set_files(files)

    def _set_files(self, files):
        self.files = files
        self.attached.setText(", ".join(name for name, _data in files))
        self.clear_files.setVisible(bool(files))
        self._update()

    def send(self):
        text = self.text.toPlainText().strip()
        if not text and not self.files:
            return None
        team = self.project.model.get(self.team.currentData()) if self.team.count() else None
        message = d.post(self.project, self.subject, self.user, text, team, self.reply_to, self.files)
        self._saved(message)
        return message

    # --- the messages of the user, and of the others for the DA ---------------------------------------------------

    def change(self, message):
        text, ok = QInputDialog.getMultiLineText(self, "Modifica il messaggio", "Testo del messaggio:",
                                                 message.get("text") or "")
        if ok and text.strip() and text.strip() != (message.get("text") or ""):
            d.edit(self.project, message, text)
            self._saved(message)

    def remove(self, message):
        if QMessageBox.question(self, "Elimina il messaggio", "Eliminare il messaggio? Resta al suo posto come "
                                "«messaggio eliminato», senza testo e senza allegati.") != QMessageBox.Yes:
            return
        d.delete(self.project, message)
        self._saved(message)

    def hide(self, message):
        d.set_hidden(self.project, message, not message.get("hidden_by_da"))
        self._saved(message)

    def _saved(self, message):
        save_project(self, self.project, {message.uuid})  # alone: the changes in progress of the sheet are not saved
        d.mark_read(self.project, self.subject)
        self.changed.emit()
