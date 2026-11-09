"""«Vista d'insieme»: which branches to overlay on the main branch and which elements to include (OverviewSetup), and
the view itself, read only, with what is approved told from what is only on the branches (OverviewWindow)."""
from html import escape

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QSplitter, QTextBrowser, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from arcadia_tool.diff.semantic import format_value, word_diff
from arcadia_tool.model.discussions import SUBJECTS, when
from arcadia_tool.model.element import is_empty, natural_key
from arcadia_tool.model.schema import GROUPS, KINDS, KINDS_BY_NAME, REF, REFS, STR, TABLE, TEXT
from arcadia_tool.storage.overview import (APPROVED, CHANGED, DIVERGENT, NEW, NOT_SHOWN, REMOVED, STATE_LABELS, STATES,
                                           OverviewBuilder)
from arcadia_tool.ui.branches import FetchWorker
from arcadia_tool.ui.diff_view import CSS, _cell_text
from arcadia_tool.ui.model_tree import TREE_FIRST
from arcadia_tool.ui.theme import CHANGE_BG, CHANGE_COLORS, GROUP_ICONS, MUTED, icon, kind_icon

UUID_ROLE = Qt.UserRole
KIND_ROLE = Qt.UserRole + 1
STATE_COLORS = {APPROVED: CHANGE_COLORS["added"], CHANGED: CHANGE_COLORS["modified"], NEW: "#0969DA",
                REMOVED: CHANGE_COLORS["removed"], DIVERGENT: "#8250DF"}
STATE_BG = {APPROVED: CHANGE_BG["added"], CHANGED: CHANGE_BG["modified"], NEW: "#DDF4FF",
            REMOVED: CHANGE_BG["removed"], DIVERGENT: "#FBEFFF"}
STATE_ICONS = {APPROVED: "mdi6.check-circle-outline", CHANGED: "mdi6.circle-edit-outline",
               NEW: "mdi6.plus-circle-outline", REMOVED: "mdi6.minus-circle-outline", DIVERGENT: "mdi6.alert-outline"}


def ordered_kinds():
    """The kinds of the view, in the order of the tree of the model."""
    kinds = [k for k in KINDS if k.name not in NOT_SHOWN]
    return sorted(kinds, key=lambda k: TREE_FIRST.index(k.name) if k.name in TREE_FIRST else len(TREE_FIRST))


def row_text(overview, entry):
    """How an element is named in the lists: the branch beside its number, as two branches can use the same number."""
    label = overview.model.label(entry.element)
    where = ", ".join(entry.branches)
    if not where:
        return label
    ident = entry.element.get("id")
    if ident and label.startswith(ident):
        return f"{ident} · {where}{label[len(ident):]}"
    return f"{label} · {where}"


def _sorted(overview, entries):
    return sorted(entries, key=lambda e: natural_key(overview.model.label(e.element)))


def kind_title(kind):
    return f"{kind.template} · {kind.plural}" if kind.template else kind.plural


# --- choosing what to see --------------------------------------------------------------------------------------------

class PrepareWorker(QThread):
    done = Signal()
    failed = Signal(str)

    def __init__(self, builder, main, sources):
        super().__init__()
        self.builder, self.main, self.sources = builder, main, sources

    def run(self):
        try:
            self.builder.build(self.main, self.sources)  # all of them: choosing among them then reads nothing
            self.done.emit()
        except Exception as exc:
            self.failed.emit(f"Lettura dei rami non riuscita: {exc or exc.__class__.__name__}")


class OverviewSetup(QDialog):
    """The branches to overlay on the main branch, the elements to include. Accepted: `overview` and shown()."""

    def __init__(self, project, credentials=None, parent=None):
        super().__init__(parent)
        self.project, self.credentials = project, credentials or {}
        self.builder = OverviewBuilder(project.repository)
        self.worker, self.main, self.sources, self.overview = None, None, [], None
        saved = project.local_settings().get("overview") or {}
        self.branches_off = set(saved.get("branches_off") or [])
        self.kinds_off, self.off = set(saved.get("kinds_off") or []), set(saved.get("off") or [])
        self._linked_saved = bool(saved.get("linked"))
        self.setWindowTitle("Vista d'insieme")
        self.resize(1000, 640)

        self.status = QLabel(objectName="muted", wordWrap=True)
        self.branch_list = QListWidget()
        self.branch_list.itemChanged.connect(lambda _item: self._branches_changed())
        self.fetch_button = QPushButton(icon("mdi6.cloud-sync-outline"), "Aggiorna dal repository")
        self.fetch_button.clicked.connect(lambda _=False: self.fetch())
        self.fetch_button.setVisible(bool(project.remote()))
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Rami da sovrapporre", objectName="formLabel"))
        self.main_label = QLabel(objectName="muted", wordWrap=True)
        left_layout.addWidget(self.main_label)
        left_layout.addWidget(self.branch_list, 1)
        left_layout.addWidget(self.fetch_button)

        self.all_button = QPushButton("Tutto")
        self.adr_button = QPushButton("Solo ADR")
        self.pending_button = QPushButton("Solo non approvati")
        self.pending_button.setToolTip("Include solo ciò che i rami hanno cambiato e che non è ancora nel ramo principale")
        self.all_button.clicked.connect(lambda _=False: self.choose_all())
        self.adr_button.clicked.connect(lambda _=False: self.choose_adrs())
        self.pending_button.clicked.connect(lambda _=False: self.choose_pending())
        presets = QHBoxLayout()
        for b in (self.all_button, self.adr_button, self.pending_button):
            presets.addWidget(b)
        presets.addStretch(1)
        self.search = QLineEdit(placeholderText="Cerca per ID, nome o ramo", objectName="search")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self._apply_search())
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.setUniformRowHeights(True)
        self.linked = QCheckBox("Includi gli elementi collegati")
        self.linked.setToolTip("Aggiunge gli elementi a cui gli elementi scelti fanno riferimento direttamente")
        self.linked.setChecked(self._linked_saved)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Elementi da includere", objectName="formLabel"))
        right_layout.addLayout(presets)
        right_layout.addWidget(self.search)
        right_layout.addWidget(self.tree, 1)
        right_layout.addWidget(self.linked)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([320, 680])
        self.create_button = QPushButton(icon("mdi6.layers-triple-outline", "white"), "Crea la vista")
        self.create_button.setProperty("primary", True)
        self.create_button.setDefault(True)
        self.create_button.clicked.connect(lambda _=False: self.create())
        cancel = QPushButton("Annulla")
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(self.status, 1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.create_button)
        layout = QVBoxLayout(self)
        layout.addWidget(split, 1)
        layout.addLayout(buttons)
        self.prepare()

    # --- reading the branches --------------------------------------------------------------------------------

    def _busy(self, text):
        self.status.setText(text)
        for w in (self.create_button, self.fetch_button, self.branch_list, self.tree):
            w.setEnabled(False)

    def prepare(self):
        self.main, self.sources = self.project.overview_sources()
        if self.main is None:
            self.status.setText("Il progetto non ha un ramo principale (main o master): non c'è una base per la vista.")
            self.create_button.setEnabled(False)
            return
        self._busy("Lettura dei rami…")
        self.worker = PrepareWorker(self.builder, self.main, self.sources)
        self.worker.done.connect(self._prepared)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _failed(self, text):
        self.status.setText(text)
        self.fetch_button.setEnabled(True)

    def fetch(self):
        self._busy("Download dei rami del repository…")
        self.worker = FetchWorker(self.project, self.credentials)
        self.worker.done.connect(self.prepare)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _prepared(self):
        self.status.clear()
        for w in (self.create_button, self.fetch_button, self.branch_list, self.tree):
            w.setEnabled(True)
        self._fill_branches()
        self._branches_changed()

    def _fill_branches(self):
        self.main_label.setText(f"Base: «{self.main.name}» @ {self.main.sha[:8]}, ciò che è approvato")
        self.branch_list.blockSignals(True)
        self.branch_list.clear()
        for s in self.sources:
            notes = [f"@ {s.sha[:8]}"]
            if s.only_here:
                notes.append("solo su questo PC")
            elif s.differs:
                notes.append("usata la versione del repository")
            item = QListWidgetItem(f"{s.name}  ({', '.join(notes)})")
            item.setData(UUID_ROLE, s.name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if s.name in self.branches_off else Qt.Checked)
            self.branch_list.addItem(item)
        self.branch_list.blockSignals(False)

    def chosen_sources(self):
        items = [self.branch_list.item(i) for i in range(self.branch_list.count())]
        names = {i.data(UUID_ROLE) for i in items if i.checkState() == Qt.Checked}
        return [s for s in self.sources if s.name in names]

    # --- the elements ----------------------------------------------------------------------------------------

    def _kind_items(self):
        for g in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(g)
            for k in range(group.childCount()):
                yield group.child(k)

    def _read_selection(self):
        """What is ticked now into kinds_off and off (what is not listed now keeps its choice)."""
        if not self.tree.topLevelItemCount():
            return
        for kind_item in self._kind_items():
            kind = kind_item.data(0, KIND_ROLE)
            children = [kind_item.child(i) for i in range(kind_item.childCount())]
            uuids = {c.data(0, UUID_ROLE) for c in children}
            self.off -= uuids
            self.kinds_off.discard(kind)
            unticked = {c.data(0, UUID_ROLE) for c in children if c.checkState(0) != Qt.Checked}
            if unticked == uuids:
                self.kinds_off.add(kind)
            else:
                self.off |= unticked

    def _branches_changed(self):
        self._read_selection()
        self.branches_off = {s.name for s in self.sources} - {s.name for s in self.chosen_sources()}
        self.overview = self.builder.build(self.main, self.chosen_sources())
        self._fill_elements()

    def _fill_elements(self):
        bold = QFont()
        bold.setWeight(QFont.DemiBold)
        muted = QBrush(QColor(MUTED))
        expanded = {k.data(0, KIND_ROLE) for k in self._kind_items() if k.isExpanded()}
        self.tree.setUpdatesEnabled(False)
        self.tree.blockSignals(True)
        self.tree.clear()
        groups = {}
        entries = {}
        for e in self.overview.shown():
            entries.setdefault(e.kind, []).append(e)
        for kind in ordered_kinds():
            if kind.name not in entries:
                continue
            group = groups.get(kind.group)
            if group is None:
                group = groups[kind.group] = QTreeWidgetItem([kind.group, ""])
                group.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                group.setIcon(0, icon(GROUP_ICONS[kind.group], "#3D4B5C"))
                group.setFont(0, bold)
            rows = []
            kind_off = kind.name in self.kinds_off
            for e in _sorted(self.overview, entries[kind.name]):
                row = QTreeWidgetItem([row_text(self.overview, e), STATE_LABELS[e.state]])
                row.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                row.setData(0, UUID_ROLE, e.uuid)
                row.setForeground(1, QBrush(QColor(STATE_COLORS[e.state])))
                row.setCheckState(0, Qt.Unchecked if kind_off or e.uuid in self.off else Qt.Checked)
                rows.append(row)
            item = QTreeWidgetItem(group, [kind_title(kind), str(len(rows))])
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            item.setIcon(0, kind_icon(kind.name))
            item.setForeground(1, muted)
            item.setData(0, KIND_ROLE, kind.name)
            item.addChildren(rows)
            item.setExpanded(kind.name in expanded)
        for name in GROUPS:  # in the order of the tree of the model
            if name in groups:
                self.tree.addTopLevelItem(groups[name])
                groups[name].setExpanded(True)
        self.tree.blockSignals(False)
        self.tree.setUpdatesEnabled(True)
        self._apply_search()

    def _apply_search(self):
        words = self.search.text().lower().split()
        for g in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(g)
            group_visible = False
            for k in range(group.childCount()):
                kind_item = group.child(k)
                visible = False
                for i in range(kind_item.childCount()):
                    row = kind_item.child(i)
                    hit = all(w in row.text(0).lower() for w in words)
                    row.setHidden(not hit)
                    visible |= hit
                kind_item.setHidden(not visible)
                if words and visible:
                    kind_item.setExpanded(True)
                group_visible |= visible
            group.setHidden(not group_visible)

    def _tick(self, wanted):
        """wanted(kind, entry): the rows ticked."""
        self.tree.setUpdatesEnabled(False)
        self.tree.blockSignals(True)
        for kind_item in self._kind_items():
            kind = kind_item.data(0, KIND_ROLE)
            for i in range(kind_item.childCount()):
                row = kind_item.child(i)
                entry = self.overview.entries[row.data(0, UUID_ROLE)]
                row.setCheckState(0, Qt.Checked if wanted(kind, entry) else Qt.Unchecked)
        self.tree.blockSignals(False)
        self.tree.setUpdatesEnabled(True)

    def choose_all(self):
        self._tick(lambda kind, entry: True)

    def choose_adrs(self):
        self._tick(lambda kind, entry: kind == "adr")

    def choose_pending(self):
        self._tick(lambda kind, entry: entry.state != APPROVED)

    def shown(self):
        """The uuids of the elements of the view."""
        found = set()
        for kind_item in self._kind_items():
            for i in range(kind_item.childCount()):
                if kind_item.child(i).checkState(0) == Qt.Checked:
                    found.add(kind_item.child(i).data(0, UUID_ROLE))
        return found | self.overview.linked(found) if self.linked.isChecked() else found

    def create(self):
        if not self.shown():
            self.status.setText("Scegli almeno un elemento da includere.")
            return
        self._read_selection()
        self.project.set_local_settings(overview={
            "branches_off": sorted(self.branches_off), "kinds_off": sorted(self.kinds_off), "off": sorted(self.off),
            "linked": self.linked.isChecked()})
        self.accept()

    def done(self, result):
        if self.worker is not None:
            self.worker.wait()
        super().done(result)


# --- the view --------------------------------------------------------------------------------------------------------

def _link(overview, uuid, shown):
    label = escape(overview.label_of(uuid))
    return f"<a href='{escape(uuid)}'>{label}</a>" if uuid in shown else label


def value_html(overview, f, value, shown):
    """A value of a field, the references to the elements in the view being links."""
    if is_empty(value):
        return "—"
    if f.type == REF:
        return _link(overview, value, shown)
    if f.type == REFS:
        return ", ".join(_link(overview, v, shown) for v in value)
    if f.type == TABLE:
        head = "".join(f"<th>{escape(c.label)}</th>" for c in f.columns)
        rows = "".join("<tr>" + "".join(f"<td>{escape(_cell_text(overview, c, row))}</td>" for c in f.columns) + "</tr>"
                       for row in value)
        return f"<table class='rows'><tr>{head}</tr>{rows}</table>"
    return escape(format_value(overview, f.type, value)).replace("\n", "<br>")


def _proposed_html(overview, f, approved, value, shown):
    """A value proposed by a branch; a text with what differs from the approved one marked word by word."""
    if f.type in (STR, TEXT) and isinstance(value or "", str) and isinstance(approved or "", str) and approved:
        html = ""
        for op, text in word_diff(approved, value or ""):
            t = escape(text).replace("\n", "<br>")
            html += f"<span class='new'>{t}</span>" if op == "+" else f"<span class='old'>{t}</span>" if op == "-" else t
        return html
    return value_html(overview, f, value, shown)


def _badge(state):
    return (f"<span style='color:{STATE_COLORS[state]}; background:{STATE_BG[state]}; font-weight:600'>"
            f"&nbsp;{STATE_LABELS[state]}&nbsp;</span>")


def _fields_html(overview, entry, shown):
    main = escape(overview.main.name)
    proposing = [p for p in entry.proposals if not p.removed]
    divergent = entry.divergent_fields
    rows = []
    for f in KINDS_BY_NAME[entry.kind].fields:
        if f.hidden:
            continue
        approved = entry.approved.values.get(f.name) if entry.approved is not None else None
        if entry.approved is None:  # new: what each branch says, once if they all say the same
            values = [(p.branch, p.fields.get(f.name)) for p in proposing]
            if all(is_empty(v) for _b, v in values):
                continue
            if f.name not in divergent:
                rows.append(f"<tr><td class='name'>{escape(f.label)}</td>"
                            f"<td>{value_html(overview, f, values[0][1], shown)}</td></tr>")
                continue
            cell = [f"<div><b>{escape(b)}:</b> {value_html(overview, f, v, shown)}</div>" for b, v in values]
        else:
            changes = [p for p in proposing if f.name in p.fields]
            if not changes:
                if not is_empty(approved):
                    rows.append(f"<tr><td class='name'>{escape(f.label)}</td>"
                                f"<td>{value_html(overview, f, approved, shown)}</td></tr>")
                continue
            cell = [f"<div><b>Approvato ({main}):</b> {value_html(overview, f, approved, shown)}</div>"]
            cell += [f"<div><b>{escape(p.branch)}:</b> {_proposed_html(overview, f, approved, p.fields[f.name], shown)}"
                     "</div>" for p in changes]
        warn = f" {_badge(DIVERGENT)}" if f.name in divergent else ""
        state = DIVERGENT if f.name in divergent else NEW if entry.approved is None else CHANGED
        rows.append(f"<tr style='background:{STATE_BG[state]}'><td class='name'>{escape(f.label)}{warn}</td>"
                    f"<td>{''.join(cell)}</td></tr>")
    return f"<table class='fields'>{''.join(rows)}</table>"


def _discussion_html(overview, entry):
    messages = overview.messages_of(entry.uuid)
    if not messages:
        return ""
    parts = ["<h3>Discussione</h3>"]
    for m in messages:
        e = m.element
        text = "<i>messaggio eliminato</i>" if e.get("deleted") else "<i>messaggio nascosto</i>" if e.get("hidden_by_da") \
            else escape(e.get("text") or "").replace("\n", "<br>")
        where = f" · {escape(', '.join(m.branches))}" if m.branches else ""
        parts.append(f"<p><b>{escape(e.get('author') or '')}</b> "
                     f"<span class='kind'>{escape(when(e.get('posted')))}{where}</span> {_badge(m.state)}<br>{text}</p>")
    return "".join(parts)


def entry_html(overview, entry, shown):
    """The sheet of an element of the view."""
    kind = KINDS_BY_NAME[entry.kind]
    where = f" · {escape(', '.join(entry.branches))}" if entry.branches else ""
    parts = [f"<style>{CSS}</style>", f"<h2>{escape(overview.model.label(entry.element))}</h2>",
             f"<div class='kind'>{escape(kind.label)}{where} &nbsp; {_badge(entry.state)}</div>"]
    removals = [p.branch for p in entry.proposals if p.removed]
    if removals:
        parts.append(f"<p class='warn'>Rimosso in: {escape(', '.join(removals))}</p>")
    parts.append(_fields_html(overview, entry, shown))
    if entry.kind in SUBJECTS:
        parts.append(_discussion_html(overview, entry))
    return "".join(parts)


class OverviewWindow(QDialog):
    """The view, read only: a window of its own, the project stays usable. reconfigure: «Cambia selezione…»."""
    reconfigure = Signal()

    def __init__(self, overview, shown, parent=None):
        super().__init__(parent)
        self.overview, self.shown = overview, set(shown)
        self.setWindowTitle("Vista d'insieme (sola lettura)")
        self.setWindowFlag(Qt.WindowMaximizeButtonHint)
        self.setModal(False)
        self.resize(1200, 760)
        names = ", ".join(s.name for s in overview.branches) or "nessuno"
        header = QLabel(f"Base: <b>{escape(overview.main.name)}</b> @ {overview.main.sha[:8]} · "
                        f"Rami sovrapposti: <b>{escape(names)}</b>", wordWrap=True)
        change = QPushButton(icon("mdi6.tune-variant"), "Cambia selezione o aggiorna…")
        change.clicked.connect(lambda _=False: self.reconfigure.emit())
        top = QHBoxLayout()
        top.addWidget(header, 1)
        top.addWidget(change)
        counts = {s: 0 for s in STATES}
        included = [e for e in overview.shown() if e.uuid in self.shown]
        for e in included:
            counts[e.state] += 1
        self.state_boxes = {}
        legend = QHBoxLayout()
        for state in STATES:
            box = QCheckBox(f"{STATE_LABELS[state]} ({counts[state]})", checked=True)
            box.setIcon(icon(STATE_ICONS[state], STATE_COLORS[state]))
            box.toggled.connect(lambda _on: self._apply_filter())
            self.state_boxes[state] = box
            legend.addWidget(box)
        legend.addStretch(1)
        self.search = QLineEdit(placeholderText="Cerca per ID, nome o ramo", objectName="search")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self._apply_filter())
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.setUniformRowHeights(True)
        self.tree.currentItemChanged.connect(lambda item, _p: self._show(item))
        self.sheet = QTextBrowser()
        self.sheet.setOpenLinks(False)
        self.sheet.anchorClicked.connect(self._follow)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.search)
        left_layout.addWidget(self.tree, 1)
        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(self.sheet)
        split.setSizes([480, 720])
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        if overview.excluded:
            notice = "; ".join(f"«{s.name}» {why}" for s, why in overview.excluded)
            layout.addWidget(QLabel(f"Rami esclusi: {escape(notice)}", objectName="muted", wordWrap=True))
        layout.addLayout(legend)
        layout.addWidget(split, 1)
        self._items = {}
        self._fill(included)
        self._apply_filter()

    def _fill(self, included):
        bold = QFont()
        bold.setWeight(QFont.DemiBold)
        muted = QBrush(QColor(MUTED))
        by_kind, groups = {}, {}
        for e in included:
            by_kind.setdefault(e.kind, []).append(e)
        for kind in ordered_kinds():
            if kind.name not in by_kind:
                continue
            group = groups.get(kind.group)
            if group is None:
                group = groups[kind.group] = QTreeWidgetItem([kind.group, ""])
                group.setFlags(Qt.ItemIsEnabled)
                group.setIcon(0, icon(GROUP_ICONS[kind.group], "#3D4B5C"))
                group.setFont(0, bold)
            item = QTreeWidgetItem(group, [kind_title(kind), ""])
            item.setFlags(Qt.ItemIsEnabled)
            item.setIcon(0, kind_icon(kind.name))
            item.setForeground(1, muted)
            rows = []
            for e in _sorted(self.overview, by_kind[kind.name]):
                row = QTreeWidgetItem([row_text(self.overview, e), STATE_LABELS[e.state]])
                row.setData(0, UUID_ROLE, e.uuid)
                row.setIcon(0, icon(STATE_ICONS[e.state], STATE_COLORS[e.state]))
                row.setForeground(1, QBrush(QColor(STATE_COLORS[e.state])))
                if e.state != APPROVED:
                    row.setFont(0, bold)  # not a colour: the row selected stays readable
                self._items[e.uuid] = row
                rows.append(row)
            item.addChildren(rows)
            item.setExpanded(any(self.overview.entries[r.data(0, UUID_ROLE)].state != APPROVED for r in rows))
        for name in GROUPS:
            if name in groups:
                self.tree.addTopLevelItem(groups[name])
                groups[name].setExpanded(True)

    def _apply_filter(self):
        states = {s for s, box in self.state_boxes.items() if box.isChecked()}
        words = self.search.text().lower().split()
        for g in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(g)
            any_kind = False
            for k in range(group.childCount()):
                kind_item = group.child(k)
                count = 0
                for i in range(kind_item.childCount()):
                    row = kind_item.child(i)
                    hit = (self.overview.entries[row.data(0, UUID_ROLE)].state in states
                           and all(w in row.text(0).lower() for w in words))
                    row.setHidden(not hit)
                    count += hit
                kind_item.setText(1, str(count))
                kind_item.setHidden(not count)
                any_kind |= bool(count)
            group.setHidden(not any_kind)

    def _show(self, item):
        uuid = item.data(0, UUID_ROLE) if item is not None else None
        if uuid:
            self.sheet.setHtml(entry_html(self.overview, self.overview.entries[uuid], self.shown))

    def _follow(self, url: QUrl):
        item = self._items.get(url.toString())
        if item is None:
            return
        if item.isHidden():  # filtered out: the link still leads to it
            self.search.clear()
            for box in self.state_boxes.values():
                box.setChecked(True)
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
