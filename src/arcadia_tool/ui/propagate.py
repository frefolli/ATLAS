"""«Propaga…» (Design Authority only): the versions of the branch in use (e.g. «master», after integrating into it the
work of a team) integrated into other branches chosen, one at a time, with the window of «Integra» (all or the
elements chosen); see MainWindow.propagate_changes."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout)

from arcadia_tool.ui.branches import FetchWorker
from arcadia_tool.ui.element_editor import card
from arcadia_tool.ui.theme import MUTED, icon

NAME_ROLE = Qt.UserRole


class PropagateDialog(QDialog):
    """The branches to propagate the versions of the branch in use to, with ticks: those missing some of them ticked
    at first; those already up to date, or with no version in common, shown but not to choose. The branches of the
    repository are downloaded first (if there is one), so that what each one lacks is known."""

    def __init__(self, project, credentials, parent=None, fetch=True):
        super().__init__(parent)
        self.project, self.credentials = project, credentials
        self.source = project.current_branch()
        self.worker = None
        self.setWindowTitle("Propaga le modifiche")
        self.resize(620, 520)
        header, header_layout = card()
        header_layout.addWidget(QLabel(f"Propaga il ramo «{self.source}»", objectName="elementTitle"))
        hint = QLabel(f"Le versioni del ramo in uso «{self.source}» vengono integrate nei rami scelti, uno alla "
                      "volta, con la finestra di integrazione: tutto o gli elementi scelti. Al termine torni sul "
                      f"ramo «{self.source}».", objectName="muted")
        hint.setWordWrap(True)
        header_layout.addWidget(hint)
        self.list = QListWidget()
        self.list.itemChanged.connect(lambda _item: self._update())
        self.status = QLabel(objectName="muted")
        self.status.setWordWrap(True)
        self.send = QCheckBox("Invia ogni ramo al repository dopo l'integrazione")
        self.send.setChecked(bool(project.remote()))
        self.send.setEnabled(bool(project.remote()))
        self.fetch_button = QPushButton(icon("mdi6.cloud-download-outline"), "Aggiorna i rami dal repository")
        self.fetch_button.clicked.connect(self.fetch)
        self.fetch_button.setVisible(bool(project.remote()))
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton(icon("mdi6.source-merge", "white"), "Propaga")
        self.ok.setProperty("primary", True)
        self.ok.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(self.fetch_button)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.ok)
        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(QLabel("Rami in cui integrare le versioni:"))
        layout.addWidget(self.list, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.send)
        layout.addLayout(buttons)
        self.fill()
        if fetch and project.remote():
            self.fetch()

    def fill(self):
        """The branches, each with how many versions of the source it lacks (the ticks chosen are kept)."""
        kept = {self.list.item(i).data(NAME_ROLE): self.list.item(i).checkState() for i in range(self.list.count())}
        self.list.blockSignals(True)
        self.list.clear()
        for name, missing in self.project.propagation_targets(self.source):
            if missing is None:
                text, choosable = f"{name}  ·  nessuna versione in comune con «{self.source}»", False
            elif missing == 0:
                text, choosable = f"{name}  ·  già aggiornato", False
            else:
                versions = "1 versione" if missing == 1 else f"{missing} versioni"
                text, choosable = f"{name}  ·  {versions} di «{self.source}» da integrare", True
            item = QListWidgetItem(text)
            item.setData(NAME_ROLE, name)
            if choosable:
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(kept.get(name, Qt.Checked))
            else:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setForeground(Qt.gray)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._update()

    def _update(self):
        n = len(self.chosen)
        self.ok.setEnabled(bool(n) and self.worker is None)
        if self.worker is None:
            self.status.setStyleSheet(f"color: {MUTED};")
            self.status.setText("Nessun ramo scelto" if not n else "1 ramo scelto" if n == 1 else f"{n} rami scelti")

    @property
    def chosen(self):
        """The names of the branches ticked, in the order of the list."""
        return [self.list.item(i).data(NAME_ROLE) for i in range(self.list.count())
                if self.list.item(i).flags() & Qt.ItemIsUserCheckable and self.list.item(i).checkState() == Qt.Checked]

    def fetch(self):
        self.fetch_button.setEnabled(False)
        self.status.setStyleSheet(f"color: {MUTED};")
        self.status.setText("Download dei rami del repository…")
        self.worker = FetchWorker(self.project, self.credentials)
        self.worker.done.connect(self._fetched)
        self.worker.failed.connect(self._failed)
        self.ok.setEnabled(False)
        self.worker.start()

    def _fetched(self):
        self.worker.wait()
        self.worker = None
        self.fetch_button.setEnabled(True)
        self.fill()

    def _failed(self, message):
        self.worker.wait()
        self.worker = None
        self.fetch_button.setEnabled(True)
        self._update()
        self.status.setStyleSheet("color: #B42318;")
        self.status.setText(f"{message}. I rami sono quelli dell'ultimo aggiornamento.")

    def done(self, result):
        if self.worker is not None:  # closed while downloading: let it finish first
            self.worker.wait()
            self.worker = None
        super().done(result)
