"""A drop-down list of choices with ticks, one or more, that stays open while they are ticked (e.g. the teams or the
domains whose SRS requirements are shown). A combo box (the same look as the others) whose list is a menu."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMenu, QPushButton, QWidget

from arcadia_tool.ui.theme import icon


class _StayingMenu(QMenu):
    """A menu whose ticks do not close it."""

    def mouseReleaseEvent(self, event):
        action = self.actionAt(event.position().toPoint())
        if action is not None and action.isCheckable() and action.isEnabled():
            action.trigger()
            return
        super().mouseReleaseEvent(event)


class MultiPick(QComboBox):
    """The choices (value, label), each with a tick; its text: what is ticked (or `empty` if nothing)."""
    changed = Signal()

    def __init__(self, empty="Scegli…", parent=None, search_title=None, chooser=None):
        super().__init__(parent)
        self.empty = empty
        # Many choices (e.g. the SRS items): a window with search and ticks instead of the menu, with this title.
        self.search_title = search_title
        # A window of its own to choose (e.g. the traceability window of the SRS items): function(values ticked) →
        # the new values, or None if cancelled.
        self.chooser = chooser
        self.addItem(empty)  # the one item: the text shown
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.setMinimumContentsLength(16)
        self.menu_ = _StayingMenu(self)
        self.actions_ = {}
        self._show_text()

    def showPopup(self):
        """The list with the ticks, under the box, as wide as it at least (a window with search, for many)."""
        if self.chooser is not None:
            chosen = self.chooser(self.values)
            if chosen is not None:
                self.set_values(chosen)
            return
        if self.search_title:
            from arcadia_tool.ui.element_editor import RefPicker

            choices = [(value, action.text()) for value, action in self.actions_.items()]
            dialog = RefPicker(choices, set(self.values), self, title=self.search_title)
            if dialog.exec():
                self.set_values(dialog.selected())
            return
        self.menu_.setMinimumWidth(self.width())
        self.menu_.popup(self.mapToGlobal(self.rect().bottomLeft()))

    def hidePopup(self):
        self.menu_.hide()

    def set_choices(self, choices, ticked=()):
        """The choices [(value, label)], those of `ticked` ticked (also those already ticked and still there)."""
        kept = set(self.values) | set(ticked)
        self.menu_.clear()
        self.actions_ = {}
        for value, label in choices:
            action = self.menu_.addAction(label)
            action.setCheckable(True)
            action.setChecked(value in kept)
            action.toggled.connect(self._toggled)
            self.actions_[value] = action
        self._show_text()

    @property
    def values(self):
        """The values ticked, in the order of the choices."""
        return [v for v, a in self.actions_.items() if a.isChecked()]

    def set_values(self, values):
        for v, a in self.actions_.items():
            a.blockSignals(True)
            a.setChecked(v in values)
            a.blockSignals(False)
        self._show_text()
        self.changed.emit()

    def text(self):
        return self.itemText(0)

    def _toggled(self, _checked):
        self._show_text()
        self.changed.emit()

    def _show_text(self):
        labels = [a.text() for a in self.actions_.values() if a.isChecked()]
        text = self.empty if not labels else labels[0] if len(labels) == 1 else f"{labels[0]} e altri {len(labels) - 1}"
        self.setItemText(0, text)
        self.setToolTip("\n".join(labels) if labels else self.empty)


class FilterButton(QWidget):
    """A filter chosen in a window of its own: the button opening it, then what is chosen (or `empty`), and a cross
    to take the filter away. values: the uuids ticked; labels: how each one is said (set_choices)."""
    changed = Signal()

    def __init__(self, text, empty, chooser, parent=None):
        super().__init__(parent)
        self.empty, self.chooser = empty, chooser
        self.labels, self.shorts, self._values = {}, {}, []
        self.button = QPushButton(icon("mdi6.filter-outline"), f"{text}…")
        self.button.setToolTip(f"Scegli {text.lower()} da mostrare, in una finestra con ricerca e spunte")
        self.button.clicked.connect(lambda _=False: self.open())
        self.summary = QLabel(objectName="muted")
        self.clear = QPushButton(icon("mdi6.close"), "")
        self.clear.setToolTip("Togli il filtro")
        self.clear.clicked.connect(lambda _=False: self.set_values([]))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.button)
        layout.addWidget(self.summary)
        layout.addWidget(self.clear)
        self._show()

    def set_choices(self, choices):
        """How the values are said [(value, label)] or [(value, label, short)]: the label alone, the short form (e.g.
        the ID) when more are chosen; those ticked and no longer there are dropped."""
        self.labels = {c[0]: c[1] for c in choices}
        self.shorts = {c[0]: c[2] for c in choices if len(c) > 2 and c[2]}
        self._values = [v for v in self._values if v in self.labels]
        self._show()

    @property
    def values(self):
        return list(self._values)

    def set_values(self, values):
        self._values = [v for v in values if v in self.labels] if self.labels else list(values)
        self._show()
        self.changed.emit()

    def open(self):
        """The window to choose; closed with «Applica», what is ticked is the filter."""
        chosen = self.chooser(self.values)
        if chosen is not None:
            self.set_values(chosen)

    def text(self):
        return self.summary.text()

    def _show(self):
        names = [self.labels.get(v, v) for v in self._values]
        if not names:
            text = self.empty
        elif len(names) == 1:
            text = names[0]
        else:
            shorts = [self.shorts.get(v) or self.labels.get(v, v) for v in self._values]
            text = ", ".join(shorts[:3]) + (f" e altri {len(shorts) - 3}" if len(shorts) > 3 else "")
        self.summary.setText(text)
        self.summary.setStyleSheet("" if names else "color: #8A94A3;")
        self.summary.setToolTip("\n".join(names))
        self.clear.setVisible(bool(names))
