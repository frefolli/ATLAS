"""«Matrice delle interfacce» (SA-5): the N² matrix of the exchanges between the domains (and the external actors),
generated from the model and drawn again when it changes. A row for each producer, a column for each user; in a cell
the data exchanged, coloured by the state of the agreement between the teams."""
from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QMenu, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from arcadia_tool.model.interfaces import agreed, datum, has_data, interface_matrix, summary
from arcadia_tool.ui.theme import ACCENT, MUTED, icon

AGREED_BG, OPEN_BG, INSIDE_BG = "#ECFDF3", "#FFF4ED", "#F2F4F7"
OPEN = "#C4320A"
SHOWN = 4  # the data written in a cell; the others in its tooltip
LEGEND = (f"<span style='background:{AGREED_BG}'>&nbsp;&nbsp;&nbsp;&nbsp;</span> tutti gli scambi concordati "
          f"&nbsp;·&nbsp; <span style='background:{OPEN_BG}'>&nbsp;&nbsp;&nbsp;&nbsp;</span> qualche scambio da "
          f"concordare &nbsp;·&nbsp; <span style='background:{INSIDE_BG}'>&nbsp;&nbsp;&nbsp;&nbsp;</span> "
          f"scambi interni al dominio &nbsp;·&nbsp; <span style='color:{MUTED}'>(dato da definire)</span>: senza "
          "Exchange Item. Righe: chi produce; colonne: chi usa. Doppio clic su una cella: apri lo scambio; su un "
          "dominio: la sua vista di contesto.")
TITLE = "Matrice delle interfacce"


def _short(model, element):
    return element.get("id") or element.get("name") or model.label(element)


class InterfacesPage(QWidget):
    """open_requested(uuid): an exchange to open; context_requested(uuid): the context of a domain."""
    open_requested = Signal(str)
    context_requested = Signal(str)

    def __init__(self, project):
        super().__init__()
        self.project = project
        self.title = QLabel(TITLE, objectName="viewTitle")
        self.counts = QLabel(objectName="muted")
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 12, 0)
        bar.addWidget(self.title)
        bar.addStretch(1)
        bar.addWidget(self.counts)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.horizontalHeader().setDefaultSectionSize(150)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.cellDoubleClicked.connect(self._cell_opened)
        self.table.horizontalHeader().sectionDoubleClicked.connect(lambda c: self._end_opened(c))
        self.table.verticalHeader().sectionDoubleClicked.connect(lambda r: self._end_opened(r))
        self.legend = QLabel(LEGEND, objectName="muted", wordWrap=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self.legend)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        """The matrix again from the model."""
        model = self.project.model
        self.matrix = matrix = interface_matrix(model)
        ends = matrix.ends
        self.table.clear()
        self.table.setRowCount(len(ends))
        self.table.setColumnCount(len(ends))
        bold = QFont(self.font())
        bold.setBold(True)
        for i, e in enumerate(ends):
            text = _short(model, e)
            for header, setter in ((QTableWidgetItem(text), self.table.setVerticalHeaderItem),
                                   (QTableWidgetItem(text), self.table.setHorizontalHeaderItem)):
                header.setToolTip(model.label(e) + ("" if e.kind == "external_actor" else
                                                   "\nDoppio clic: la sua vista di contesto"))
                header.setIcon(icon("mdi6.account-outline" if e.kind == "external_actor"
                                    else "mdi6.view-grid-outline", ACCENT))
                setter(i, header)
        for r, source in enumerate(ends):
            for c, target in enumerate(ends):
                cell = matrix.cell(source.uuid, target.uuid)
                item = QTableWidgetItem()
                if cell is not None:
                    self._fill(item, cell, source, target, r == c)
                elif r == c:
                    item.setBackground(QBrush(QColor(INSIDE_BG)))
                self.table.setItem(r, c, item)
        interfaces, exchanges, to_agree, undefined = summary(matrix)
        text = (f"{interfaces} interfacce · {exchanges} scambi · {to_agree} da concordare · "
                f"{undefined} senza dato")
        if matrix.without_domain:
            text += f" · {matrix.without_domain} di funzioni senza dominio, non mostrati"
        self.counts.setText(text)

    def _fill(self, item, cell, source, target, inside):
        model = self.project.model
        open_ = [fe for fe in cell.exchanges if not agreed(fe)]
        lines = [datum(model, fe) for fe in cell.exchanges[:SHOWN]]
        if cell.count > SHOWN:
            lines.append(f"+{cell.count - SHOWN} altri")
        item.setText("\n".join(lines))
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
        item.setBackground(QBrush(QColor(INSIDE_BG if inside else OPEN_BG if open_ else AGREED_BG)))
        if open_:
            item.setForeground(QBrush(QColor(OPEN)))
        elif not all(has_data(model, fe) for fe in cell.exchanges):
            item.setForeground(QBrush(QColor(MUTED)))
        rows = "".join(
            f"<tr><td>{escape(fe.get('id') or '')}</td><td>{escape(datum(model, fe))}</td>"
            f"<td style='color:{OPEN if not agreed(fe) else MUTED}'>{escape(fe.get('status') or 'senza stato')}"
            "</td></tr>" for fe in cell.exchanges)
        where = "dentro" if inside else f"da {escape(_short(model, source))} a"
        item.setToolTip(f"<b>{cell.count} scamb{'io' if cell.count == 1 else 'i'} {where} "
                        f"{escape(_short(model, target))}</b><table>{rows}</table>")
        item.setData(Qt.UserRole, [fe.uuid for fe in cell.exchanges])

    def _cell_opened(self, row, column):
        item = self.table.item(row, column)
        uuids = item.data(Qt.UserRole) if item is not None else None
        if not uuids:
            return
        if len(uuids) == 1:
            self.open_requested.emit(uuids[0])
            return
        model = self.project.model
        menu = QMenu(self)
        for uuid in uuids:
            fe = model.get(uuid)
            if fe is not None:
                menu.addAction(icon("mdi6.open-in-app"), f"{fe.get('id') or ''} · {datum(model, fe)}",
                               lambda _=False, u=uuid: self.open_requested.emit(u))
        rect = self.table.visualItemRect(item)
        menu.exec(self.table.viewport().mapToGlobal(rect.bottomLeft()))

    def _end_opened(self, index):
        if 0 <= index < len(self.matrix.ends):
            end = self.matrix.ends[index]
            if end.kind == "domain":
                self.context_requested.emit(end.uuid)
