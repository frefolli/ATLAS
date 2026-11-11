"""A drop-down list of choices with ticks, one or more, that stays open while they are ticked (e.g. the teams or the
domains whose SRS requirements are shown). A combo box (the same look as the others) whose list is a menu."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QMenu


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

    def __init__(self, empty="Scegli…", parent=None):
        super().__init__(parent)
        self.empty = empty
        self.addItem(empty)  # the one item: the text shown
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.setMinimumContentsLength(16)
        self.menu_ = _StayingMenu(self)
        self.actions_ = {}
        self._show_text()

    def showPopup(self):
        """The list with the ticks, under the box, as wide as it at least."""
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
