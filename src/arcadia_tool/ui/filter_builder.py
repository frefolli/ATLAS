"""Conditions on the columns of a list, one per row (column, operator, value), each joined to the next one by the
logical operator of its fourth choice, AND or OR (empty on the last one); AND binds before OR (see model.filters).
Under the search of the catalogue of the ADR."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from arcadia_tool.model.filters import AND, OPERATORS, OR, WITHOUT_VALUE, Condition, parts
from arcadia_tool.ui.theme import MUTED, icon

# The fourth choice of a row: nothing (the last condition), AND or OR with the next one.
CONNECTORS = (("", None), ("AND", AND), ("OR", OR))


class ConditionRow(QWidget):
    changed = Signal()
    removed = Signal(object)
    connector_chosen = Signal(object)  # AND or OR chosen: a next condition is wanted

    def __init__(self, columns, values_of, parent=None):
        super().__init__(parent)
        self.values_of = values_of
        self.column = QComboBox()
        for key, label in columns:
            self.column.addItem(label, key)
        self.column.setToolTip("La colonna del catalogo")
        self.operator = QComboBox()
        self.operator.addItems(OPERATORS)
        self.value = QComboBox()
        self.value.setEditable(True)
        self.value.setMinimumContentsLength(18)
        self.value.lineEdit().setPlaceholderText("valore (scegli o scrivi)")
        self.connector = QComboBox()
        for label, key in CONNECTORS:
            self.connector.addItem(label, key)
        self.connector.setMinimumContentsLength(4)
        self.connector.setToolTip("Come si lega alla condizione successiva: AND (tutte e due) oppure OR (almeno una); "
                                  "vuoto sull'ultima")
        self.remove = QPushButton(icon("mdi6.close"), "")
        self.remove.setToolTip("Togli la condizione")
        self.remove.clicked.connect(lambda: self.removed.emit(self))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.column)
        layout.addWidget(self.operator)
        layout.addWidget(self.value, 1)
        layout.addWidget(self.connector)
        layout.addWidget(self.remove)
        self.refresh_values()
        self.column.currentIndexChanged.connect(lambda _i: (self.refresh_values(), self.changed.emit()))
        self.operator.currentIndexChanged.connect(lambda _i: (self._operator_changed(), self.changed.emit()))
        self.value.currentTextChanged.connect(lambda _t: self.changed.emit())
        self.connector.currentIndexChanged.connect(self._connector_changed)

    def refresh_values(self):
        """The values of the column, to choose from (or a value written by hand)."""
        text = self.value.currentText()
        self.value.blockSignals(True)
        self.value.clear()
        self.value.addItems(self.values_of(self.column.currentData()))
        self.value.setEditText(text)
        self.value.blockSignals(False)

    def _operator_changed(self):
        self.value.setEnabled(self.operator.currentText() not in WITHOUT_VALUE)

    def _connector_changed(self, _index):
        if self.connector.currentData():
            self.connector_chosen.emit(self)
        self.changed.emit()

    def condition(self, join=AND):
        """The condition of the row; join: how it is joined to the one before it (the connector of that row)."""
        return Condition(self.column.currentData(), self.operator.currentText(), self.value.currentText(), join)


class FilterBuilder(QWidget):
    """«Aggiungi condizione», the rows of the conditions, «Togli i filtri», and what is wrong in the expression."""
    changed = Signal()

    def __init__(self, columns, values_of, parent=None):
        super().__init__(parent)
        self.columns, self.values_of = columns, values_of
        self.rows = []
        self.add_button = QPushButton(icon("mdi6.filter-plus-outline"), "Aggiungi condizione")
        self.add_button.setToolTip("Filtra per una colonna del catalogo: colonna, operatore, valore e, per legarla "
                                   "alla condizione successiva, AND oppure OR")
        self.add_button.clicked.connect(lambda: self.add())
        self.clear_button = QPushButton(icon("mdi6.filter-remove-outline"), "Togli i filtri")
        self.clear_button.clicked.connect(self.clear)
        self.status = QLabel(objectName="muted")
        self.status.setWordWrap(True)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self.add_button)
        top.addWidget(self.clear_button)
        top.addWidget(self.status, 1)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(self.rows_layout)
        layout.addLayout(top)
        self._update()

    def add(self, column=None, operator=None, value=None):
        """A new row (with its column, operator and value, if given). The row before it, if it had no AND or OR, is
        joined to it with AND."""
        if self.rows and not self.rows[-1].connector.currentData():
            last = self.rows[-1].connector
            last.blockSignals(True)
            last.setCurrentIndex(last.findData(AND))
            last.blockSignals(False)
        row = ConditionRow(self.columns, self.values_of, self)
        if column is not None:
            row.column.setCurrentIndex(max(row.column.findData(column), 0))
        if operator is not None:
            row.operator.setCurrentText(operator)
        if value is not None:
            row.value.setEditText(value)
        row.changed.connect(self._changed)
        row.removed.connect(self._remove)
        row.connector_chosen.connect(self._connector_chosen)
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        self._changed()
        return row

    def _connector_chosen(self, row):
        """AND or OR on the last row: the next condition, to fill."""
        if row is self.rows[-1]:
            self.add()

    def _remove(self, row):
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._changed()

    def clear(self):
        for row in list(self.rows):
            self.rows.remove(row)
            row.setParent(None)
            row.deleteLater()
        self._changed()

    def refresh_values(self):
        for row in self.rows:
            row.refresh_values()

    @property
    def problem(self):
        """Why the expression cannot be applied (a row followed by another one without AND or OR), or None."""
        missing = [i + 1 for i, row in enumerate(self.rows[:-1]) if not row.connector.currentData()]
        if missing:
            return f"Manca AND oppure OR dopo la condizione {', '.join(map(str, missing))}."
        return None

    @property
    def conditions(self):
        """The conditions of the rows, in order, each joined to the one before it by the AND or OR of that row
        (empty if the expression cannot be applied: see problem)."""
        if self.problem:
            return []
        return [row.condition(self.rows[i - 1].connector.currentData() if i else AND)
                for i, row in enumerate(self.rows)]

    def _changed(self):
        self._update()
        self.changed.emit()

    def _update(self):
        self.clear_button.setVisible(bool(self.rows))
        problem = self.problem
        if problem:
            self.status.setStyleSheet("color: #B42318;")
            self.status.setText(f"{problem} Il filtro non è applicato.")
        else:
            self.status.setStyleSheet(f"color: {MUTED};")
            self.status.setText("AND ha la precedenza su OR: «A AND B OR C» vale «(A AND B) OR C»."
                                if len(self.rows) > 1 else "")


def distinct_values(texts):
    """The values of a column to choose from: each text, and each value of a list («DF01, DF02»), sorted."""
    from arcadia_tool.model.element import natural_key

    found = {p for t in texts for p in parts(t) if p}
    return sorted(found, key=lambda v: natural_key(v.lower()))
