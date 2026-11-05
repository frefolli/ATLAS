"""Versioni › Ricevi dal repository: the versions published by the others on the working branch, merged with
those of this PC (see storage.merge). What both changed in different ways is chosen here, row by row."""
import re

import yaml
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QProgressBar, QPushButton,
                               QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from arcadia_tool.accounts import git_host
from arcadia_tool.model.element import Model
from arcadia_tool.model.schema import KINDS_BY_NAME
from arcadia_tool.model.serialization import loads
from arcadia_tool.storage.merge import OURS, THEIRS
from arcadia_tool.storage.project import Receive
from arcadia_tool.ui.theme import MUTED, icon

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
CHOICES = ((None, "— scegli —"), (OURS, "Mantieni quella di questo PC"), (THEIRS, "Usa quella ricevuta"))
SETTINGS_LABELS = {"project.yaml": "Impostazioni del progetto", "checks.yaml": "Impostazioni delle verifiche"}
VALUE_LENGTH = 160


class ReceiveWorker(QThread):
    done = Signal(object)  # the Receive
    failed = Signal(str)

    def __init__(self, project, credentials, prepare=None):
        super().__init__()
        self.project, self.credentials, self.prepare = project, credentials, prepare

    def run(self):
        try:
            self.done.emit(self.prepare() if self.prepare else self.project.prepare_receive(**self.credentials))
        except Exception as exc:
            self.failed.emit(f"Operazione non riuscita: {exc or exc.__class__.__name__}")


class ReceiveDialog(QDialog):
    """applied: the versions were received (the project must be opened again); merged: a version of integration
    was recorded (to send); publish_first: the user asked to publish the changes of this PC first.
    integrate: (branch, version): Rami › Integra, the branch integrated into the one in use (same merge)."""

    def __init__(self, project, credentials, author=None, parent=None, integrate=None, user=None):
        super().__init__(parent)
        self.project, self.credentials, self.author, self.user = project, credentials, author, user
        self.integrate = integrate
        self.moved_to = None  # «Sposta su un nuovo ramo»: the branch the versions of this PC went to
        self.receive, self.worker, self._lookup = None, None, None
        self.applied = self.merged = self.publish_first = False
        self.result = None
        self.setWindowTitle("Integra ramo" if integrate else "Ricevi dal repository")
        self.resize(980, 380)
        url, branch = project.remote(), project.push_branch()
        title = QLabel(f"Integrazione del ramo «{integrate[0]}» nel ramo in uso «{project.current_branch()}»"
                       if integrate else f"Ricezione dal ramo «{branch}» di {git_host(url) or url}",
                       objectName="cardTitle")
        self.status = QLabel("Preparazione dell'integrazione…" if integrate else "Connessione al repository…",
                             objectName="muted")
        self.status.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.versions = QLabel(objectName="muted")
        self.versions.setWordWrap(True)
        self.versions.setTextFormat(Qt.RichText)
        self.conflicts = QTableWidget(0, 4)
        self.conflicts.setHorizontalHeaderLabels(["Scheda e campo", "Su questo PC", "Ricevuto", "Scelta"])
        header = self.conflicts.horizontalHeader()
        for column, mode in enumerate((QHeaderView.Interactive, QHeaderView.Stretch, QHeaderView.Stretch,
                                       QHeaderView.Fixed)):
            header.setSectionResizeMode(column, mode)
        header.resizeSection(0, 260)
        header.resizeSection(3, 270)  # the choice (a list in the cell)
        self.conflicts.verticalHeader().setVisible(False)
        self.conflicts.setWordWrap(True)
        self.conflicts.setVisible(False)
        self.all_ours = QPushButton("Tutte quelle di questo PC")
        self.all_ours.clicked.connect(lambda: self._choose_all(OURS))
        self.all_theirs = QPushButton("Tutte quelle ricevute")
        self.all_theirs.clicked.connect(lambda: self._choose_all(THEIRS))
        self.retry = QPushButton(icon("mdi6.refresh"), "Riprova")
        self.retry.clicked.connect(self.start)
        self.publish_button = QPushButton(icon("mdi6.cloud-upload-outline"), "Pubblica le modifiche…")
        self.publish_button.clicked.connect(self._publish_first)
        self.move_button = QPushButton(icon("mdi6.source-branch-plus"), "Sposta le mie versioni su un nuovo ramo…")
        self.move_button.setToolTip("Le tue versioni non inviate passano a un nuovo ramo, da inviare; il ramo "
                                    "principale torna come sul repository. La DA integrerà poi il tuo ramo.")
        self.move_button.clicked.connect(self._move_to_branch)
        self.apply_button = QPushButton(icon("mdi6.cloud-download-outline", "white"), "Ricevi")
        self.apply_button.setProperty("primary", True)
        self.apply_button.clicked.connect(self.apply)
        self.close_button = QPushButton("Chiudi")
        self.close_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(self.all_ours)
        buttons.addWidget(self.all_theirs)
        buttons.addStretch()
        for b in (self.retry, self.publish_button, self.move_button, self.close_button, self.apply_button):
            buttons.addWidget(b)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        for w in (title, self.bar, self.status, self.versions):
            layout.addWidget(w)
        # Integra: the preview of the result (the branch in use → after the merge, as in «Pubblica»), over the
        # conflicts left to the user; it follows the choices.
        self.preview = self.preview_view = None
        self._preview_timer = QTimer(self, singleShot=True, interval=300)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self.conflicts_title = QLabel(objectName="formLabel")
        self.conflicts_title.setVisible(False)
        if integrate:
            from arcadia_tool.ui.versions import maximizable
            maximizable(self)
            self.resize(1240, 800)
            self.apply_button.setText("Integra")
            self.apply_button.setIcon(icon("mdi6.source-merge", "white"))
            self.close_button.setText("Annulla integrazione")
            self.close_button.setToolTip("Chiude senza integrare: il progetto non cambia")
            self.preview = QWidget()
            self.preview.setLayout(QVBoxLayout())
            self.preview.layout().setContentsMargins(0, 0, 0, 0)
            self.preview.setVisible(False)
            lower = QWidget()
            lower_layout = QVBoxLayout(lower)
            lower_layout.setContentsMargins(0, 0, 0, 0)
            lower_layout.addWidget(self.conflicts_title)
            lower_layout.addWidget(self.conflicts, 1)
            splitter = QSplitter(Qt.Vertical)
            splitter.addWidget(self.preview)
            splitter.addWidget(lower)
            splitter.setSizes([520, 220])
            layout.addWidget(splitter, 1)
        else:
            layout.addWidget(self.conflicts, 1)
        layout.addLayout(buttons)
        self._buttons()

    def exec(self):
        self.start()
        return super().exec()

    def start(self):
        self._buttons()
        self.bar.setVisible(True)
        self.status.setStyleSheet(f"color: {MUTED};")
        self.status.setText("Download delle versioni del ramo…")
        prepare = (lambda: self.project.prepare_integration(*self.integrate)) if self.integrate else None
        self.worker = ReceiveWorker(self.project, self.credentials, prepare)
        self.worker.done.connect(self.show_receive)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _buttons(self, apply=False, conflicts=False, retry=False, publish=False, move=False):
        self.apply_button.setVisible(apply)
        self.move_button.setVisible(move)
        self.all_ours.setVisible(conflicts)
        self.all_theirs.setVisible(conflicts)
        self.retry.setVisible(retry)
        self.publish_button.setVisible(publish)

    def _failed(self, message):
        if self.worker is not None:
            self.worker.wait()
        self.bar.setVisible(False)
        self.status.setStyleSheet("color: #B42318;")
        self.status.setText(message)
        self._buttons(retry=True)

    # --- what is received -------------------------------------------------------------------------

    def show_receive(self, receive):
        if self.worker is not None:
            self.worker.wait()
        self.receive = receive
        self.bar.setVisible(False)
        branch, into = receive.branch, receive.into
        if receive.state == Receive.UP_TO_DATE:
            self.status.setText(f"Il ramo in uso «{into}» contiene già tutte le versioni di «{branch}»: nulla da "
                                "integrare." if into else
                                f"Nessuna nuova versione sul ramo «{branch}»: il progetto è aggiornato.")
            return
        if receive.state == Receive.UNRELATED:
            self.status.setStyleSheet("color: #B42318;")
            self.status.setText(f"I rami «{branch}» e «{into}» non hanno nessuna versione in comune: sono progetti "
                                "nati separatamente, e integrarli raddoppierebbe voci SRS, domini, funzioni e team. "
                                "Non si integrano: scegli uno dei due come base e riporta in esso il lavoro "
                                "dell'altro.")
            return
        if receive.state == Receive.PUBLISH_FIRST and into:
            self.status.setText("Qui ci sono modifiche non ancora pubblicate. Pubblicale (o scartale) prima di "
                                "integrare un altro ramo: l'integrazione è una versione a sé.")
            self._buttons(publish=True)
            return
        if receive.state == Receive.NO_BRANCH:
            self.status.setText(f"Il ramo «{branch}» non è ancora nel repository: inviando le tue versioni viene "
                                "creato.")
            return
        count = len(receive.incoming)
        self.versions.setText(f"<b>{count} {'versione ricevuta' if count == 1 else 'versioni ricevute'}</b>: " +
                              "; ".join(f"{v.title} ({v.author.split('<')[0].strip()}, {v.timestamp:%d/%m %H:%M})"
                                        for v in receive.incoming[:8]) + ("…" if count > 8 else ""))
        if receive.state == Receive.PUBLISH_FIRST:
            self.status.setText("Sia tu sia i colleghi avete pubblicato nuove versioni, e qui ci sono modifiche "
                                "non ancora pubblicate. Pubblicale prima: poi le versioni vengono integrate in una "
                                "nuova versione.")
            self._buttons(publish=True)
            return
        denied = self._merge_denied()
        if denied:  # only the Design Authority merges into the main branch
            self.status.setStyleSheet("color: #B42318;")
            self.status.setText(denied if into else
                                f"{denied}\n\nQui ci sono versioni tue non ancora inviate e sul repository versioni "
                                "dei colleghi: unirle sarebbe un'unione nel ramo principale. Sposta le tue versioni su "
                                "un nuovo ramo e invialo: la DA lo integrerà.")
            self._buttons(move=not into)
            return
        result = receive.result
        if into:
            what = (f"Le versioni di «{branch}» e quelle di «{into}» vengono integrate in una nuova versione di "
                    f"«{into}», da inviare poi al repository. Come con «Ricevi», l'unione è per scheda e per campo, "
                    "gli identificativi doppi vengono rinumerati e le tracciature collegate riallineate."
                    if receive.state == Receive.MERGE else
                    f"«{into}» non ha versioni che «{branch}» non abbia: prende le versioni di «{branch}» così come "
                    "sono.")
        else:
            what = (f"Le versioni ricevute e le tue ({len(self.project.unsent_versions())} non ancora inviate) "
                    "vengono integrate in una nuova versione, da inviare poi al repository."
                    if receive.state == Receive.MERGE else
                    "Il progetto viene aggiornato con le versioni ricevute; le modifiche non ancora pubblicate "
                    "restano da pubblicare.")
        if receive.foreign:
            count = len(receive.foreign)
            which = "versione è un'unione fatta" if count == 1 else "versioni sono unioni fatte"
            what += (f"\n\nAttenzione: {count} {which} "
                     "fuori da ATLAS (con Git): gli identificativi potrebbero essere doppi e le tracciature non "
                     "allineate. Dopo, esegui «Verifica modello» (GEN-02, ID duplicati) e correggi le schede.")
        if result.conflicts:
            what += (f"\n\n{len(result.conflicts)} modifiche sono state fatte in modo diverso qui e nelle versioni "
                     "ricevute: scegli quale tenere per ciascuna.")
        else:
            merged = f", {len(result.merged)} schede integrate campo per campo" if result.merged else ""
            what += f"\n\n{len(result.received)} file ricevuti{merged}, nessun conflitto."
        self.status.setText(what)
        self._fill_conflicts(result.conflicts)
        self._buttons(apply=True, conflicts=bool(result.conflicts))
        self._update_apply()
        if self.integrate:
            self._show_preview(result)

    def _fill_conflicts(self, conflicts):
        self.conflicts.setRowCount(len(conflicts))
        self.conflicts.setVisible(bool(conflicts))
        if conflicts:
            self.resize(self.width(), 620)
        for row, c in enumerate(conflicts):
            where = QTableWidgetItem(self._where(c))
            where.setData(Qt.UserRole, c.key)
            self.conflicts.setItem(row, 0, where)
            for column, value in ((1, c.ours), (2, c.theirs)):
                text = self._value(c, value)
                item = QTableWidgetItem(text if len(text) <= VALUE_LENGTH else text[:VALUE_LENGTH] + "…")
                item.setToolTip(text)
                self.conflicts.setItem(row, column, item)
            choice = QComboBox()
            choice.setMinimumWidth(250)
            for data, label in CHOICES:
                choice.addItem(label, data)
            choice.currentIndexChanged.connect(self._update_apply)
            choice.currentIndexChanged.connect(lambda _i: self._preview_timer.start())
            self.conflicts.setCellWidget(row, 3, choice)
        self.conflicts.resizeRowsToContents()

    # --- the preview of the integration ---------------------------------------------------------------------------

    def _show_preview(self, result):
        """The branch in use → after the merge (the choices made so far; the conflicts not chosen yet as here)."""
        from arcadia_tool.diff.semantic import diff_models
        from arcadia_tool.storage.merge import merged_model
        from arcadia_tool.ui.diff_view import DiffView

        diff = diff_models(self.project.model, merged_model(result.files))
        if self.preview_view is not None:
            self.preview_view.setParent(None)
            self.preview_view.deleteLater()
        into, branch = self.receive.into, self.receive.branch
        self.preview_view = DiffView(diff, f"«{into}» ora", f"«{into}» dopo l'integrazione di «{branch}»")
        self.preview.layout().addWidget(self.preview_view)
        self.preview.setVisible(True)
        conflicts = self.conflicts.rowCount()
        auto = len(result.received) + len(result.merged)
        self.conflicts_title.setText(
            f"Unite automaticamente: {auto} schede ({len(result.merged)} campo per campo"
            + (f", {len(result.renumbered)} identificativi rinumerati" if result.renumbered else "")
            + (f", {len(result.relinked)} tracciature riallineate" if result.relinked else "") + ")"
            + (f" · da risolvere: {conflicts} {'conflitto' if conflicts == 1 else 'conflitti'} (scegli per ciascuno "
               "quale versione tenere: l'anteprima si aggiorna)" if conflicts else " · nessun conflitto"))
        self.conflicts_title.setVisible(True)
        self.preview_result = result

    def _refresh_preview(self):
        if self.receive is not None and self.integrate:
            self._show_preview(self.receive.merge(self.choices()))

    def _element(self, conflict):
        data = self.receive.ours.get(conflict.path) or self.receive.theirs_files.get(conflict.path)
        try:
            return loads(data.decode("utf-8")) if data else None
        except Exception:
            return None

    def _where(self, conflict):
        if conflict.uuid is None:
            name = SETTINGS_LABELS.get(conflict.path, conflict.path)
            return f"{name}: {conflict.field}" if conflict.field else name
        element = self._element(conflict)
        if element is None:
            return conflict.path
        schema = KINDS_BY_NAME[element.kind]
        label = " · ".join(str(v) for v in (element.get("id"), element.get("name") or element.get("title")) if v)
        sheet = f"{schema.label} {label}".strip()
        if conflict.field is None:
            return f"{sheet}: eliminata da una parte, modificata dall'altra"
        f = schema.field(conflict.field)
        return f"{sheet} › {f.label if f is not None else conflict.field}"

    def _label(self, uuid):
        if self._lookup is None:
            elements = []
            for files in (self.receive.theirs_files, self.receive.ours):
                for path, data in files.items():
                    if path.startswith("model/") and path.endswith(".yaml"):
                        elements.append(loads(data.decode("utf-8")))
            self._lookup = Model(elements)
        element = self._lookup.get(uuid)
        return self._lookup.label(element) if element is not None else uuid

    def _value(self, conflict, value):
        if conflict.field is None:  # the whole file: there, or deleted
            return "(eliminata)" if value is None else "(presente, modificata)"
        if value is None:
            return "(vuoto)"
        if isinstance(value, str) and UUID.match(value):
            return self._label(value)
        if isinstance(value, list) and all(isinstance(v, str) and UUID.match(v) for v in value):
            return ", ".join(self._label(v) for v in value)
        if isinstance(value, (list, dict)):
            return yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=200).strip()
        return str(value)

    # --- choices and receiving ---------------------------------------------------------------------

    def choices(self):
        result = {}
        for row in range(self.conflicts.rowCount()):
            choice = self.conflicts.cellWidget(row, 3).currentData()
            if choice:
                result[self.conflicts.item(row, 0).data(Qt.UserRole)] = choice
        return result

    def _choose_all(self, choice):
        for row in range(self.conflicts.rowCount()):
            combo = self.conflicts.cellWidget(row, 3)
            combo.setCurrentIndex(combo.findData(choice))

    def _update_apply(self, *_args):
        missing = self.conflicts.rowCount() - len(self.choices())
        self.apply_button.setEnabled(missing == 0)
        self.apply_button.setToolTip(f"Scegli ancora {missing} modifiche" if missing else "")

    def _merge_denied(self):
        """Why the user may not make the merge prepared (into the main branch), or None."""
        r = self.receive
        if r is None or r.state != Receive.MERGE:
            return None
        return self.project.main_denied(self.user, r.into or r.branch)

    def _move_to_branch(self):
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        from arcadia_tool.ui.branches import suggested_name
        name, ok = QInputDialog.getText(self, "Sposta su un nuovo ramo", "Nome del nuovo ramo:",
                                        text=suggested_name(self.project, self.user))
        if not ok or not name.strip():
            return
        try:
            self.project.move_unsent_to_branch(name.strip())
        except Exception as exc:
            QMessageBox.warning(self, "Sposta su un nuovo ramo", str(exc))
            return
        self.moved_to = name.strip()
        self.accept()

    def apply(self):
        if self.receive is None or self._merge_denied():
            return
        self.result = self.project.apply_receive(self.receive, self.choices(), self.author)
        if self.result.resolved:
            self.applied = True
            self.merged = self.receive.state == Receive.MERGE
            self.accept()

    def _publish_first(self):
        self.publish_first = True
        self.accept()

    def reject(self):
        if self.worker is not None and self.worker.isRunning():
            return  # not while downloading: the window closes when the server has answered
        super().reject()
