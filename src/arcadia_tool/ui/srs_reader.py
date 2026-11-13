"""Reading view of the imported SRS: the whole specification, chapter by chapter, item after item.

Items are shown with their full text in document order, can be filtered by chapter 9 category and
searched; several items can be selected (Shift+arrows, Ctrl/Shift+click) and deleted together. From the row of a
section its domains are chosen (A4), from the row of a clause its system functions and its derived requirements.
"""
from html import escape

from PySide6.QtCore import QAbstractListModel, QEvent, QModelIndex, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QKeySequence, QPainter, QShortcut, QTextDocument
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListView, QMenu, QMessageBox, QProgressDialog, QPushButton, QStyle, QStyledItemDelegate,
                               QTabBar, QToolTip, QVBoxLayout, QWidget)

from arcadia_tool.importers.srs_pdf import chapter_of_item
from arcadia_tool.model.analysis import is_mine, mark_denied, marks_by_requirement, toggle, who_text
from arcadia_tool.model.adr import item_domains
from arcadia_tool.model.coverage import derivable
from arcadia_tool.model.element import natural_key
from arcadia_tool.ui.element_editor import image_size, load_pixmap
from arcadia_tool.ui.multi_pick import MultiPick
from arcadia_tool.ui.srs_edit_mode import SrsEditMode, edit_mode_button
from arcadia_tool.ui.theme import ACCENT, ACCENT_SOFT, BORDER, MUTED, TEXT, icon

CATEGORIES = ("Bordo", "Terra", "Definizione", "Informativa", "Altro")
NO_CATEGORY = "Senza categoria"
CATEGORY_COLORS = {"Bordo": ("#1A5FB4", "#E3EEFB"), "Terra": ("#8A4B00", "#FDF0DC"),
                   "Definizione": ("#5E3C99", "#EFE8FA"), "Informativa": ("#4B5563", "#EEF1F5"),
                   "Altro": ("#6B7280", "#F3F4F6"), NO_CATEGORY: ("#B42318", "#FEE4E2")}
HEADINGS = {"Capitolo": 15, "Sezione": 12.5, "Titolo": 11}
ELEMENT_ROLE = Qt.UserRole
NUMBER_WIDTH = 150
INDENT = {"Voce": 28}
SLOW_LAYOUT_ITEMS = 300
FIGURE_SCALE = 1.6  # figures are rendered at 2x; shown slightly larger than on paper
HIGHLIGHT = "#FFE58F"
# The row of a clause of the team of the user within a section of another team (e.g. received by a reallocation).
TEAM_CLAUSE_BG, TEAM_CLAUSE_HOVER = "#FFF7D6", "#FFF0B8"
# Whose clauses are shown (see SrsReader.scope_domains).
ALL_CLAUSES, MY_TEAM, BY_TEAMS, BY_DOMAINS = "all", "mine", "teams", "domains"
SCOPES = (("Tutti i requisiti", ALL_CLAUSES), ("Requisiti del mio team", MY_TEAM), ("Dei team…", BY_TEAMS),
          ("Dei domini funzionali…", BY_DOMAINS))


def document_order(model):
    """Requirements in specification order: depth-first along the parent relation, siblings by their position
    in the document (procedure rows S0, S1, D2… are not in alphabetical order), else by number."""
    elements = [e for e in model if e.kind == "requirement"]
    uuids = {e.uuid for e in elements}
    children = {}
    for e in elements:
        parent = e.get("parent")
        children.setdefault(parent if parent in uuids else None, []).append(e)
    for siblings in children.values():
        siblings.sort(key=lambda e: (e.get("sequence") is None, e.get("sequence") or 0,
                                     natural_key(e.get("id") or "")))
    ordered, stack = [], list(reversed(children.get(None, [])))
    while stack:
        e = stack.pop()
        ordered.append(e)
        stack.extend(reversed(children.get(e.uuid, [])))
    return ordered


def chapter_of(element):
    """The appendix of a chapter (A.3.x) is shown with its chapter."""
    return chapter_of_item(element.get("id"))


class SrsListModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.elements = []

    def set_elements(self, elements):
        self.beginResetModel()
        self.elements = elements
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.elements)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        e = self.elements[index.row()]
        if role == ELEMENT_ROLE:
            return e
        if role == Qt.DisplayRole:
            return f"{e.get('id')} {e.get('title') or ''} {e.get('text') or ''}"
        return None


MARGIN_X = 14
PAD_TOP, PAD_BOTTOM, HEADING_PAD_TOP = 6, 8, 16
CHIPS_WIDTH = 140
CHIP_GAP = 4
WRAP = Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop
# «Analizzato» of a clause (see model.analysis): its button shows who has taken it in charge. Its colours: (border and
# text, background) when nobody has, when others have, when the user has.
ANALYZED = "analyzed"
ANALYZED_STYLES = {"none": (MUTED, "white"), "others": ("#15803D", "#ECFDF3"), "mine": ("white", "#15803D")}
# Actions in the row of a section (domains, A4) and of a clause (system functions, derived requirements).
ROW_ACTIONS = {"section": (("domains", "Domini…", "Alloca la sezione ai domini funzionali (principale e "
                                                   "contributori)"),),
               "clause": (("functions", "Mappa a Funzione", "Mappa la clausola alle funzioni di sistema"),
                          ("derive", "Deriva…", "Deriva uno o più requisiti dalla clausola"),
                          ("share", "Condividi", "Propone di condividere la clausola tra più domini: crea l'ADR "
                                                 "già compilata (Clausole condivise)"),
                          ("exclude", "Escludi", "Propone di non mappare la clausola su nessun dominio: crea l'ADR "
                                                 "già compilata (Clausole non mappate)"),
                          (ANALYZED, "Non analizzato", "Segna che hai preso in carico la clausola; un altro clic "
                                                      "toglie il tuo segno"),
                          ("links", "Collega…", "Le altre voci SRS che la clausola richiama, include o da cui "
                                                "dipende")),
               "item": (("derive", "Deriva…", "Deriva uno o più requisiti dalla voce (punto di elenco, riga di "
                                              "tabella…); la tracciabilità alle funzioni è quella della clausola"),)}
ACTION_GAP = 6
# The badges of a row, drawn like its buttons: (text and border, background). The domains of a section: principal
# (True), contributing (False); the system functions of a clause: mapped to it, or to its section; its derived
# requirements.
DOMAIN_BADGES = {True: ("#1F5FBF", "#E6F0FF"), False: ("#5B6B7C", "#F1F3F6"),
                 "function": ("#0E7490", "#E0F5F9"), "inherited": ("#5B6B7C", "#F1F3F6"),
                 "derived": ("#7C3AED", "#F3EEFF"), "link": ("#B45309", "#FEF3C7")}
BADGE_TIPS = {True: "Dominio principale della sezione (A4)", False: "Dominio che contribuisce alla sezione (A4)",
              "derived": "Requisito derivato (SA-4) dalla voce"}


def row_kind(element):
    """«section» for a section (three numbers), «clause» for a clause (four numbers or more, and its sub-clauses),
    «item» for a list item or a table row (derivable, traced with its clause), None for a chapter."""
    if element.get("item_type") == "Sezione":
        return "section"
    if not derivable(element):
        return None
    return "item" if element.get("item_type") == "Voce" else "clause"


class ItemDelegate(QStyledItemDelegate):
    """Draws an item like a page of the specification: number, full text, category chips.

    Painting uses plain QPainter text layout (no HTML documents): measuring thousands of items stays fast,
    and heights are cached per width.
    """

    action_clicked = Signal(str, str)  # uuid of the item, action (see ROW_ACTIONS)
    team_clauses = frozenset()  # uuids of the rows with the background of the clauses of the team (see SrsReader)

    def __init__(self, view, project=None):
        super().__init__(view)
        self.view = view
        self.project = project
        self.links = None  # function(element) → what the item is allocated to, shown in its row of actions
        # function(element) → [(text, principal)]: the domains of a section, drawn as badges (None: the text of links)
        self.domain_badges = None
        # function(element) → [(text, style)]: the functions and derived requirements of a clause, as badges
        self.link_badges = None
        # function(element) → (label, style of ANALYZED_STYLES, who has analysed it): the button «Analizzato»
        self.analysis = None
        self._sizes = {}
        self._pixmaps = {}
        self._figure_sizes = {}  # (width, height) of the figures: their layout does not decode them
        self.highlight = ""  # searched text, highlighted in the items (lower case)
        base = view.font()
        self.fonts = {"text": QFont(base), "bold": QFont(base), "italic": QFont(base), "chip": QFont(base)}
        self.fonts["bold"].setWeight(QFont.DemiBold)
        self.fonts["italic"].setItalic(True)
        self.fonts["chip"].setPointSizeF(base.pointSizeF() * 0.82)
        self.fonts["chip"].setWeight(QFont.DemiBold)
        for item_type, size in HEADINGS.items():
            f = QFont(base)
            f.setPointSizeF(size)
            f.setWeight(QFont.DemiBold)
            self.fonts[item_type] = f
        self.metrics = {key: QFontMetrics(f) for key, f in self.fonts.items()}
        self._chip_widths = {}

    def clear_cache(self):
        self._sizes.clear()

    def invalidate(self, uuid):
        for key in [k for k in self._sizes if k[0] == uuid]:
            del self._sizes[key]
        self._pixmaps.pop(uuid, None)
        self._figure_sizes.pop(uuid, None)

    def _pixmap(self, element):
        """The image of a figure: decoded only to paint it (the rows shown)."""
        rel = element.values.get("figure")
        if not rel or self.project is None:
            return None
        if element.uuid not in self._pixmaps:
            self._pixmaps[element.uuid] = load_pixmap(self.project, rel)
        return self._pixmaps[element.uuid]

    def _figure_size(self, element):
        rel = element.values.get("figure")
        if not rel or self.project is None:
            return None
        if element.uuid not in self._figure_sizes:
            self._figure_sizes[element.uuid] = image_size(self.project, rel)
        return self._figure_sizes[element.uuid]

    @staticmethod
    def _image_size(size, width):
        # Figures are rendered at 2x: show them at about their size on paper, never wider than the text.
        w = min(width, int(size[0] / FIGURE_SCALE))
        return w, int(size[1] * w / size[0])

    def measure(self, elements, progress=None):
        """The heights of the items not measured yet, before the view lays them out (the first opening of the
        catalogue: seconds); progress(done, total) every few items."""
        width = self.view.viewport().width()
        missing = [e for e in elements if (e.uuid, width, self.highlight) not in self._sizes]
        for n, element in enumerate(missing, 1):
            *_, height = self._layout(element, QRect(0, 0, width, 0))
            self._sizes[(element.uuid, width, self.highlight)] = QSize(width, height)
            if progress is not None and (n % 50 == 0 or n == len(missing)):
                progress(n, len(missing))

    def cached(self, uuid):
        return (uuid, self.view.viewport().width(), self.highlight) in self._sizes

    def _highlighted(self, key, colour, text, width):
        """Rich-text document of a block with the searched text highlighted, or None if it does not occur."""
        term = self.highlight
        if not term or term not in text.lower():
            return None
        lower, parts, start = text.lower(), [], 0
        while True:
            found = lower.find(term, start)
            if found < 0:
                parts.append(escape(text[start:]))
                break
            parts.append(escape(text[start:found]))
            parts.append(f"<span style='background-color:{HIGHLIGHT}; color:{TEXT};'>"
                         f"{escape(text[found:found + len(term)])}</span>")
            start = found + len(term)
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setDefaultFont(self.fonts[key])
        doc.setHtml(f"<div style='color:{colour};'>{''.join(parts).replace(chr(10), '<br>')}</div>")
        doc.setTextWidth(width)
        return doc

    # --- layout (shared by sizeHint and paint) ---------------------------------------------------------

    def _blocks(self, element):
        """(font key, colour, text) blocks of the body, in order."""
        title, text = element.get("title") or "", element.get("text") or ""
        if element.get("item_type") in HEADINGS:
            blocks = [(element.get("item_type"), TEXT, f"{element.get('id') or ''}   {title}".strip())]
            if text:
                blocks.append(("text", MUTED, text))
            return blocks
        blocks = []
        if title:
            blocks.append(("bold", TEXT, title))
        if text:
            blocks.append(("text", TEXT, text))
        if not blocks:
            blocks.append(("italic", MUTED, element.get("import_note") or "Nessun testo"))
        return blocks

    def _text_height(self, key, text, width):
        metrics = self.metrics[key]
        if "\n" not in text and metrics.horizontalAdvance(text) <= width:
            return metrics.height()  # one line: much cheaper than laying out the wrapped text
        return metrics.boundingRect(QRect(0, 0, width, 100000), WRAP, text).height()

    def _chip_width(self, category):
        if category not in self._chip_widths:
            self._chip_widths[category] = self.metrics["chip"].horizontalAdvance(category) + 14
        return self._chip_widths[category]

    def _chip_rows(self, categories, width):
        metrics = self.metrics["chip"]
        rows, row, used = [], [], 0
        for c in categories or [NO_CATEGORY]:
            w = self._chip_width(c)
            if row and used + w > width:
                rows.append(row)
                row, used = [], 0
            row.append((c, w))
            used += w + CHIP_GAP
        if row:
            rows.append(row)
        return rows, metrics.height() + 4

    def _layout(self, element, rect):
        heading = element.get("item_type") in HEADINGS
        left = rect.x() + MARGIN_X + INDENT.get(element.get("item_type"), 0)
        top = rect.y() + (HEADING_PAD_TOP if heading else PAD_TOP)
        right = rect.right() - MARGIN_X
        if heading:
            body_left, chips_left = left, None
        else:
            body_left, chips_left = left + NUMBER_WIDTH, right - CHIPS_WIDTH
        body_width = max((chips_left - 12 if chips_left else right) - body_left, 120)
        kind = row_kind(element)
        # A section: the badges of its domains right of its title (which leaves them up to half of the row).
        badges = (self.domain_badges(element) or []) if self.domain_badges and kind == "section" else []
        badge_box, chip_h = None, self.metrics["chip"].height() + 8
        room = 0
        if badges:
            want = sum(self.metrics["chip"].horizontalAdvance(t) + 22 for t, _p in badges) + ACTION_GAP * (len(badges) - 1)
            room = min(want, body_width // 2)
        placed, y = [], top
        for n, (key, colour, text) in enumerate(self._blocks(element)):
            width = body_width - room - 12 if n == 0 and room else body_width
            doc = self._highlighted(key, colour, text, width)
            if doc is not None:
                h = int(doc.size().height())
                placed.append(("rich", None, doc, QRect(body_left, y, width, h)))
            else:
                h = self._text_height(key, text, width)
                placed.append((key, colour, text, QRect(body_left, y, width, h)))
            if n == 0 and room:
                title_w = min(self.metrics[key].horizontalAdvance(text), width)
                line = self.metrics[key].height()
                badge_box = QRect(body_left + title_w + 12, y + (line - chip_h) // 2, room, chip_h)
            y += h + 2
        size = self._figure_size(element)
        if size is not None:
            w, h = self._image_size(size, body_width)
            placed.append(("image", None, element, QRect(body_left, y + 4, w, h)))
            y += h + 10
        height = y - top
        chips = None
        if chips_left is not None:
            rows, chip_h = self._chip_rows(element.get("category"), CHIPS_WIDTH)
            chips = (chips_left, top, rows, chip_h)
            height = max(height, len(rows) * (chip_h + CHIP_GAP), self.metrics["bold"].height())
        actions = None
        if kind:  # a line below the text: what the item is allocated to, and the buttons to change it
            line_h = self.metrics["chip"].height() + 8
            line_top = top + height + 4
            x, buttons = right, []
            for name, label, _ in reversed(ROW_ACTIONS[kind]):
                w = self.metrics["chip"].horizontalAdvance(label) + 22
                if name == ANALYZED and self.analysis is not None:  # as wide as «Non analizzato» at least: the
                    label = self.analysis(element)[0]               # other buttons stay where they are
                    w = max(w, self.metrics["chip"].horizontalAdvance(label) + 22)
                x -= w
                buttons.insert(0, (name, label, QRect(x, line_top, w, line_h)))
                x -= ACTION_GAP
            actions = (QRect(body_left, line_top, max(x - 8 - body_left, 40), line_h), buttons, badge_box, badges)
            height += line_h + 6
        return left, top, placed, chips, actions, height + (top - rect.y()) + PAD_BOTTOM

    def _badge_places(self, box, badges):
        """Where the badges go in the box, from the left: [(rect, badge)]; then (rect, None) for «+n», the badges
        that do not fit. A badge: (text, style[, what it means, shown when the mouse is on it])."""
        metrics = self.metrics["chip"]
        places, x, right = [], box.left(), box.right()
        for n, badge in enumerate(badges):
            rest = len(badges) - n - 1
            more = metrics.horizontalAdvance(f"+{rest}") + 18 if rest else 0
            width = min(metrics.horizontalAdvance(badge[0]) + 22, right - x - more)
            if width < 60:  # no room left: how many are not shown
                places.append((QRect(x, box.top(), right - x, box.height()), None, len(badges) - n))
                break
            places.append((QRect(x, box.top(), width, box.height()), badge, 0))
            x += width + ACTION_GAP
        return places

    def _paint_domain_badges(self, painter, box, badges):
        """The badges of a row (the domains of a section, the functions of a clause…), from the left; those that do
        not fit are counted («+2»)."""
        metrics = self.metrics["chip"]
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        for chip, badge, hidden in self._badge_places(box, badges):
            if badge is None:
                painter.setPen(QColor(MUTED))
                painter.drawText(chip, Qt.AlignLeft | Qt.AlignVCenter, f"+{hidden}")
                break
            fg, bg = DOMAIN_BADGES[badge[1]]
            painter.setPen(QColor(fg))
            painter.setBrush(QColor(bg))
            painter.drawRoundedRect(chip.adjusted(0, 0, -1, -1), 6, 6)
            painter.drawText(chip.adjusted(10, 0, -10, 0), Qt.AlignCenter,
                             metrics.elidedText(badge[0], Qt.ElideRight, chip.width() - 20))
        painter.restore()

    def badge_tip(self, index, pos):
        """What the badge under a point of the viewport means (e.g. how a function is mapped), or None."""
        element = index.data(ELEMENT_ROLE)
        if element is None or not row_kind(element):
            return None
        *_, actions, _ = self._layout(element, self.view.visualRect(index))
        if actions is None:
            return None
        text_box, _buttons, badge_box, badges = actions
        links = self.link_badges(element) if self.link_badges and row_kind(element) in ("clause", "item") else []
        for box, listed in ((badge_box, badges), (text_box, links if not badges else [])):
            if box is None or not listed:
                continue
            for chip, badge, hidden in self._badge_places(box, listed):
                if chip.contains(pos):
                    if badge is None:
                        return "Altri: " + ", ".join(b[0] for b in listed[len(listed) - hidden:])
                    return badge[0] + "\n" + (badge[2] if len(badge) > 2 else BADGE_TIPS.get(badge[1], ""))
        return None

    def helpEvent(self, event, view, option, index):
        if event.type() == QEvent.ToolTip:
            tip = self.badge_tip(index, event.pos())
            if tip is None and self.analysis is not None and self.button_at(index, event.pos()) == ANALYZED:
                tip = self.analysis(index.data(ELEMENT_ROLE))[2]
            if tip:
                QToolTip.showText(event.globalPos(), tip, view)
                return True
        return super().helpEvent(event, view, option, index)

    def button_at(self, index, pos):
        """Action of the button of the row under a point of the viewport, or None."""
        element = index.data(ELEMENT_ROLE)
        if element is None or not row_kind(element):
            return None
        *_, actions, _ = self._layout(element, self.view.visualRect(index))
        for name, _, box in actions[1] if actions else ():
            if box.contains(pos):
                return name
        return None

    def editorEvent(self, event, model, option, index):
        """A click on a button of a row runs its action (and does not change the selection)."""
        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick):
            name = self.button_at(index, event.position().toPoint())
            if name is not None:
                if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                    self.action_clicked.emit(index.data(ELEMENT_ROLE).uuid, name)
                return True
        return super().editorEvent(event, model, option, index)

    def sizeHint(self, option, index):
        element = index.data(ELEMENT_ROLE)
        width = self.view.viewport().width()
        key = (element.uuid, width, self.highlight)
        if key not in self._sizes:
            *_, height = self._layout(element, QRect(0, 0, width, 0))
            self._sizes[key] = QSize(width, height)
        return self._sizes[key]

    # --- painting ------------------------------------------------------------------------------------

    def paint(self, painter, option, index):
        element = index.data(ELEMENT_ROLE)
        rect = option.rect
        painter.save()
        team_clause = element is not None and element.uuid in self.team_clauses
        if option.state & QStyle.State_Selected:
            painter.fillRect(rect, QColor(ACCENT_SOFT))
            painter.fillRect(rect.x(), rect.y(), 3, rect.height(), QColor(ACCENT))
        elif team_clause:
            painter.fillRect(rect, QColor(TEAM_CLAUSE_HOVER if option.state & QStyle.State_MouseOver
                                          else TEAM_CLAUSE_BG))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(rect, QColor("#F6F8FB"))
        left, top, placed, chips, actions, _ = self._layout(element, rect)
        if chips is not None:
            ident = element.get("id") or ""
            number_box = QRect(left, top, NUMBER_WIDTH - 10, rect.height())
            painter.setFont(self.fonts["bold"])
            if self.highlight and self.highlight in ident.lower():
                painter.fillRect(self.metrics["bold"].boundingRect(number_box, WRAP, ident).adjusted(-2, 0, 2, 0),
                                 QColor(HIGHLIGHT))
            painter.setPen(QColor(ACCENT))
            painter.drawText(number_box, WRAP, ident)
        for key, colour, content, box in placed:
            if key == "rich":
                painter.save()
                painter.translate(box.topLeft())
                content.drawContents(painter)
                painter.restore()
                continue
            if key == "image":
                pixmap = self._pixmap(content)
                if pixmap is not None and not pixmap.isNull():
                    painter.setRenderHint(QPainter.SmoothPixmapTransform)
                    painter.drawPixmap(box, pixmap)
                painter.setPen(QColor(BORDER))
                painter.drawRect(box.adjusted(-1, -1, 0, 0))
                continue
            painter.setFont(self.fonts[key])
            painter.setPen(QColor(colour))
            painter.drawText(box, WRAP, content)
        if chips is not None:
            chips_left, y, rows, chip_h = chips
            painter.setFont(self.fonts["chip"])
            painter.setRenderHint(QPainter.Antialiasing)
            for row in rows:
                x = chips_left + CHIPS_WIDTH - sum(w for _, w in row) - CHIP_GAP * (len(row) - 1)
                for c, w in row:
                    fg, bg = CATEGORY_COLORS.get(c, CATEGORY_COLORS["Altro"])
                    chip = QRect(x, y, w, chip_h)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(bg))
                    painter.drawRoundedRect(chip, 8, 8)
                    painter.setPen(QColor(fg))
                    painter.drawText(chip, Qt.AlignCenter, c)
                    x += w + CHIP_GAP
                y += chip_h + CHIP_GAP
        if actions is not None:
            text_box, buttons, badge_box, badges = actions
            painter.setFont(self.fonts["chip"])
            painter.setPen(QColor(MUTED))
            links = self.link_badges(element) if self.link_badges and row_kind(element) in ("clause", "item") else []
            if badges and badge_box is not None:  # right of the title: the line below has only the buttons
                self._paint_domain_badges(painter, badge_box, badges)
                painter.setFont(self.fonts["chip"])
            elif links:  # the functions and the derived requirements of a clause, left of its buttons
                self._paint_domain_badges(painter, text_box, links)
                painter.setFont(self.fonts["chip"])
            else:
                text = self.links(element) if self.links else ""
                painter.drawText(text_box, Qt.AlignLeft | Qt.AlignVCenter,
                                 self.metrics["chip"].elidedText(text, Qt.ElideRight, text_box.width()))
            painter.setRenderHint(QPainter.Antialiasing)
            for name, label, box in buttons:
                fg, bg = ACCENT, "white"
                if name == ANALYZED and self.analysis is not None:
                    fg, bg = ANALYZED_STYLES[self.analysis(element)[1]]
                painter.setPen(QColor(fg if fg != "white" else bg))
                painter.setBrush(QColor(bg))
                painter.drawRoundedRect(box.adjusted(0, 0, -1, -1), 6, 6)
                painter.setPen(QColor(fg))
                painter.drawText(box, Qt.AlignCenter, label)
        painter.setPen(QColor("#EEF1F5"))
        painter.drawLine(rect.x() + MARGIN_X, rect.bottom(), rect.right() - MARGIN_X, rect.bottom())
        painter.restore()


class SrsView(QListView):
    def resizeEvent(self, event):
        if event.size().width() != event.oldSize().width():
            self.itemDelegate().clear_cache()
            super().resizeEvent(event)
            self.scheduleDelayedItemsLayout()
        else:
            super().resizeEvent(event)


class SrsReader(QWidget):
    open_element = Signal(str)
    derive_requested = Signal(str)  # a derived requirement (SA-4) to create from an SRS item
    elements_deleted = Signal()
    window_toggled = Signal()  # «Apri in altra finestra» / «Riporta nelle schede»
    elements_changed = Signal(list)  # elements changed from a row (domains of a section, functions of a clause)
    elements_created = Signal()  # derived requirements created from a row
    clause_declared = Signal(str, str)  # «Condividi» or «Escludi» of a clause: the list (see model_tree), its uuid
    analysis_changed = Signal()  # «Analizzato» of a clause: the mark saved (a change to publish)

    def __init__(self, project, edit_mode=None, user_of=None):
        super().__init__()
        self.project = project
        self.user_of = user_of or (lambda: None)  # the user logged in now (who marks «Analizzato»)
        self._marks = {}
        self.chapter = None
        self._go_to_later = None  # asked while not visible: its rows are laid out only when shown
        self._pending_refresh = True
        self._refreshing = False
        self.edit_mode = edit_mode or SrsEditMode()
        self.edit_mode.changed.connect(self._selection_changed)

        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.currentChanged.connect(self._chapter_changed)

        self.search = QLineEdit(placeholderText="Cerca nel testo, per numero o per variabile", objectName="search")
        self.search.addAction(icon("mdi6.magnify"), QLineEdit.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.category_boxes = {}
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Categoria:", objectName="muted"))
        for c in CATEGORIES + (NO_CATEGORY,):
            box = QCheckBox(c)
            box.setChecked(True)
            box.toggled.connect(self.refresh)
            fg, _ = CATEGORY_COLORS[c]
            box.setStyleSheet(f"QCheckBox {{ color: {fg}; font-weight: 600; }}")
            self.category_boxes[c] = box
            filters.addWidget(box)
        filters.addSpacing(16)
        self.show_headings = QCheckBox("Mostra titoli e sezioni")
        self.show_headings.setChecked(True)
        self.show_headings.toggled.connect(self.refresh)
        filters.addWidget(self.show_headings)
        # The rows of the clauses of the team of the user in sections of other teams: light yellow, unless unticked.
        self.highlight_team = QCheckBox("Evidenzia requisiti team")
        self.highlight_team.setChecked(True)
        self.highlight_team.setToolTip("Sfondo giallo chiaro per le clausole del tuo team dentro sezioni di altri "
                                       "team (es. ricevute per riallocazione)")
        self.highlight_team.toggled.connect(self._highlight_toggled)
        filters.addWidget(self.highlight_team)
        filters.addStretch()
        # Whose requirements, under the categories: all, of the team of the user (allocated to its domains), of one or
        # more teams, of one or more functional domains.
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Requisiti:", objectName="muted"))
        self.scope = QComboBox()
        self.scope.setSizeAdjustPolicy(QComboBox.AdjustToContents)  # its texts never cut
        for label, key in SCOPES:
            self.scope.addItem(label, key)
        self.scope.currentIndexChanged.connect(self._scope_changed)
        scope_row.addWidget(self.scope)
        self.scope_pick = MultiPick()
        self.scope_pick.changed.connect(self.refresh)
        self.scope_pick.setVisible(False)
        scope_row.addWidget(self.scope_pick)
        self.scope_note = QLabel(objectName="muted")  # the teams of the user, or why there are none
        self.scope_note.setVisible(False)
        scope_row.addWidget(self.scope_note)
        scope_row.addStretch()

        self.count = QLabel(objectName="muted")
        self.delete_button = QPushButton(icon("mdi6.trash-can-outline"), "Elimina selezionate")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected)
        self.edit_mode_button = edit_mode_button(self.edit_mode)
        self.window_button = QPushButton()
        self.window_button.clicked.connect(self.window_toggled)
        self.coverage_button = QPushButton(icon("mdi6.chart-donut"), "Report di copertura…")
        self.coverage_button.setToolTip("Le voci di bordo e di definizione coperte e scoperte (dominio, funzione di "
                                        "sistema, requisito derivato) e la copertura del subset")
        self.coverage_button.clicked.connect(lambda _=False: self.show_coverage())
        self.set_detached(False)
        top_row = QHBoxLayout()
        top_row.addWidget(self.search, 1)
        top_row.addWidget(self.count)
        top_row.addWidget(self.coverage_button)
        top_row.addWidget(self.edit_mode_button)
        top_row.addWidget(self.delete_button)
        top_row.addWidget(self.window_button)

        self.model = SrsListModel()
        self.view = SrsView()
        self.view.setModel(self.model)
        self.delegate = ItemDelegate(self.view, project)
        self.delegate.links = self._links_text
        self.delegate.domain_badges = self._domain_badges
        self.delegate.link_badges = self._link_badges
        self.delegate.analysis = self._analysis
        self.delegate.team_clauses = set()  # see _team_clauses
        self.delegate.action_clicked.connect(self.run_action)
        self.view.setItemDelegate(self.delegate)
        self._links = {}
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.view.setMouseTracking(True)
        self.view.setUniformItemSizes(False)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Always shown: otherwise its appearance narrows the view and every item is measured again.
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.view.setStyleSheet(f"QListView {{ background: white; border: 1px solid {BORDER}; border-radius: 6px; }}")
        self.view.doubleClicked.connect(self._double_clicked)
        self.view.selectionModel().selectionChanged.connect(self._selection_changed)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        QShortcut(QKeySequence.Delete, self.view, activated=self.delete_selected)

        hint = QLabel("Sezioni: i badge sono i domini (blu il principale, grigi i contributori), «Domini…» le alloca. "
                      "Clausole: i badge sono le funzioni mappate (azzurre; grigie se mappate alla sezione) e i "
                      "requisiti derivati (viola); «Mappa a Funzione» le mappa "
                      "alle funzioni di sistema, «Deriva…» crea uno o più requisiti derivati, «Condividi» ed «Escludi» "
                      "creano l'ADR per condividerle tra domini o non mapparle, «Collega…» indica le voci che la "
                      "clausola richiama, include o da cui dipende (badge gialli: → verso, ← da altre voci), "
                      "«Non analizzato» segna che l'hai presa "
                      "in carico (col mouse sopra: chi l'ha analizzata). In giallo le clausole del tuo team dentro "
                      "sezioni di altri team. Doppio clic apre la voce. "
                      "Selezione multipla: Maiusc + frecce, Ctrl + clic o Maiusc + clic (Ctrl + A per tutte); in "
                      "modalità modifica, Canc elimina le voci selezionate.",
                      objectName="muted")
        hint.setWordWrap(True)
        header = QFrame(objectName="card")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        title = QLabel(f"{project.baseline or 'SUBSET-026'}", objectName="elementTitle")
        header_layout.addWidget(title)
        header_layout.addWidget(self.tabs)
        header_layout.addLayout(top_row)
        header_layout.addLayout(filters)
        header_layout.addLayout(scope_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(header)
        layout.addWidget(self.view, 1)
        layout.addWidget(hint)
        self.reload()

    # --- data ----------------------------------------------------------------------------------

    def reload(self):
        """Re-read the requirements from the model (after an import or a deletion)."""
        self.all = document_order(self.project.model)
        self._rebuild_links()
        # What the filters need, computed once per item instead of at every filter change.
        self.rows = []
        self.parents = {e.uuid: e.values.get("parent") for e in self.all}
        for e in self.all:
            values = e.values
            self.rows.append((e, chapter_of(e), values.get("item_type") in HEADINGS,
                              frozenset(values.get("category") or ()) or frozenset((NO_CATEGORY,)),
                              f"{values.get('id') or ''} {values.get('title') or ''} {values.get('text') or ''}".lower()))
        counts = {}
        for _, chapter, *_ in self.rows:
            if chapter is not None:
                counts[chapter] = counts.get(chapter, 0) + 1
        chapters = sorted(counts)
        self.tabs.blockSignals(True)
        while self.tabs.count():
            self.tabs.removeTab(0)
        self.tabs.addTab(f"Tutti ({len(self.all)})")
        self.tabs.setTabData(0, None)
        for c in chapters:
            i = self.tabs.addTab(f"Capitolo {c} ({counts[c]})")
            self.tabs.setTabData(i, c)
        index = next((i for i in range(self.tabs.count()) if self.tabs.tabData(i) == self.chapter), 0)
        self.tabs.setCurrentIndex(index)
        self.chapter = self.tabs.tabData(index)
        self.tabs.blockSignals(False)
        self._update_category_counts()
        self._fill_scope_choices()  # teams or domains created or deleted meanwhile
        self.refresh()

    def _update_category_counts(self):
        counts = dict.fromkeys(self.category_boxes, 0)
        for _, chapter, heading, categories, _ in self.rows:
            if not heading and (self.chapter is None or chapter == self.chapter):
                for c in categories:
                    if c in counts:
                        counts[c] += 1
        for c, box in self.category_boxes.items():
            box.setText(f"{c} ({counts[c]})")

    def _chapter_changed(self, index):
        self.chapter = self.tabs.tabData(index)
        self._update_category_counts()
        self.refresh()

    def _scope_changed(self, _index=None):
        """«Tutte le clausole», «Dei team», «Dei domini»: the teams or the domains to choose, ticked."""
        self.scope_pick.set_choices([])  # another list: nothing ticked
        self._fill_scope_choices()
        self.refresh()

    def _fill_scope_choices(self):
        """The teams or the domains of the model now (those ticked stay ticked); the teams of the user."""
        model, key = self.project.model, self.scope.currentData()
        self.scope_pick.setVisible(key in (BY_TEAMS, BY_DOMAINS))
        self.scope_note.setVisible(key == MY_TEAM)
        if key == MY_TEAM:
            teams = self._my_teams()
            self.scope_note.setText(
                "i domini di " + ", ".join(model.label(t) for t in teams) if teams else
                "nessun requisito: non sei membro di nessun team del progetto" if self.user_of() else
                "nessun requisito: nessun utente collegato")
        if key == BY_TEAMS:
            teams = sorted(model.of_kind("team"), key=lambda t: natural_key(t.get("id") or t.get("name") or ""))
            self.scope_pick.empty = "Scegli i team…"
            self.scope_pick.set_choices([(t.uuid, model.label(t)) for t in teams])
        elif key == BY_DOMAINS:
            domains = sorted(model.of_kind("domain"), key=lambda d: natural_key(d.get("id") or d.get("name") or ""))
            self.scope_pick.empty = "Scegli i domini…"
            self.scope_pick.set_choices([(d.uuid, model.label(d)) for d in domains])

    def scope_domains(self):
        """The domains whose clauses are shown, or None (all the clauses): those chosen, or those of the teams
        chosen (none chosen yet: no clause)."""
        key = self.scope.currentData()
        if key == ALL_CLAUSES:
            return None
        if key == MY_TEAM:
            chosen = {t.uuid for t in self._my_teams()}
            return {d.uuid for d in self.project.model.of_kind("domain") if d.get("team") in chosen}
        chosen = set(self.scope_pick.values)
        if key == BY_DOMAINS:
            return chosen
        return {d.uuid for d in self.project.model.of_kind("domain") if d.get("team") in chosen}

    def user_changed(self):
        """Another user logged in: «Requisiti del mio team» shows the requirements of their teams; the clauses of
        their teams in sections of other teams are highlighted."""
        if self.scope.currentData() == MY_TEAM:
            self._fill_scope_choices()
        self.refresh()

    def _highlight_toggled(self, on):
        """Only the background of the rows changes: no new layout."""
        delegate = self.view.itemDelegate()
        delegate.team_clauses = self._team_clauses(self.model.elements) if on else set()
        self.view.viewport().update()

    def _team_clauses(self, elements):
        """The clauses (of `elements`) of the teams of the user within a section none of their domains has (a mixed
        case, e.g. clauses received by a reallocation): their rows are highlighted."""
        from arcadia_tool.model.adr import section_of

        teams = {t.uuid for t in self._my_teams()}
        own = {d.uuid for d in self.project.model.of_kind("domain") if d.get("team") in teams}
        if not own:
            return set()
        model, found, sections = self.project.model, set(), {}
        for e in elements:
            if e.get("item_type") in HEADINGS or own.isdisjoint(item_domains(model, e)):
                continue
            section = section_of(model, e)
            if section is None or section is e:
                continue
            if section.uuid not in sections:
                sections[section.uuid] = own.isdisjoint(item_domains(model, section))
            if sections[section.uuid]:
                found.add(e.uuid)
        return found

    def _my_teams(self):
        """The teams of the user logged in."""
        from arcadia_tool.model.teams import memberships

        user = self.user_of()
        return [t for t, _row in memberships(self.project.model, user)] if user is not None else []

    def selected_categories(self):
        return {c for c, box in self.category_boxes.items() if box.isChecked()}

    def showEvent(self, event):
        super().showEvent(event)
        if self._pending_refresh:
            self.refresh()
        if self._go_to_later:
            uuid, self._go_to_later = self._go_to_later, None
            self.go_to(uuid)

    def refresh(self, *_):
        if not self.isVisible():
            # Item heights depend on the final width of the view: lay out only once it is shown.
            self._pending_refresh = True
            return
        if self._refreshing:  # asked again while the loading bar lets the events through: this one does it
            return
        self._refreshing = True
        try:
            self._refresh()
        finally:
            self._refreshing = False

    def _refresh(self):
        self._pending_refresh = False
        wanted = self.selected_categories()
        text = self.search.text().strip().lower()
        domains = self.scope_domains()
        filtered = bool(text) or wanted != set(self.category_boxes) or domains is not None
        items, needed_headings = set(), set()
        for e, chapter, heading, categories, haystack in self.rows:
            if heading or (self.chapter is not None and chapter != self.chapter):
                continue
            if categories.isdisjoint(wanted) or (text and text not in haystack):
                continue
            if domains is not None and domains.isdisjoint(item_domains(self.project.model, e)):
                continue
            items.add(e.uuid)
            if filtered:
                # With a filter, keep only the headings that contain something that is shown.
                parent = self.parents.get(e.uuid)
                while parent and parent not in needed_headings:
                    needed_headings.add(parent)
                    parent = self.parents.get(parent)
        shown = []
        for e, chapter, heading, _, _ in self.rows:
            if self.chapter is not None and chapter != self.chapter:
                continue
            if heading:
                if self.show_headings.isChecked() and (not filtered or e.uuid in needed_headings):
                    shown.append(e)
            elif e.uuid in items:
                shown.append(e)
        # Heights are cached per item and width: only items never measured cost time (first opening).
        delegate = self.view.itemDelegate()
        delegate.highlight = text
        delegate.team_clauses = self._team_clauses(shown) if self.highlight_team.isChecked() else set()
        slow = sum(1 for e in shown if not delegate.cached(e.uuid)) > SLOW_LAYOUT_ITEMS
        loading = None
        if slow:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        if slow and not text:
            # The first opening (or a new width): a window with a loading bar while the items are measured. Not
            # while searching: the items found are measured again with the text highlighted, as it is typed.
            loading = QProgressDialog("Caricamento del catalogo delle voci SRS…", None, 0, 0, self)
            loading.setWindowTitle("Voci SRS")
            loading.setWindowModality(Qt.WindowModal)
            loading.setMinimumDuration(0)
            loading.setAutoClose(False)
            loading.setAutoReset(False)
            loading.setMinimumWidth(420)
            loading.show()
            QApplication.processEvents()

            def progress(done, total):
                loading.setLabelText(f"Caricamento del catalogo delle voci SRS: {done} di {total} voci…")
                loading.setMaximum(total)
                loading.setValue(done)
                QApplication.processEvents()
        try:
            if loading is not None:
                delegate.measure(shown, progress)
            self.model.set_elements(shown)
            self.view.doItemsLayout()
        finally:
            if loading is not None:
                loading.close()
                loading.deleteLater()
            if slow:
                QApplication.restoreOverrideCursor()
        self.count.setText("1 voce" if len(items) == 1 else f"{len(items)} voci")
        self._selection_changed()

    def set_detached(self, detached):
        """The catalogue is shown in its own window (detached) or in a tab of the main window."""
        self.detached = detached
        if detached:
            self.window_button.setIcon(icon("mdi6.dock-window"))
            self.window_button.setText("Riporta nelle schede")
            self.window_button.setToolTip("Riporta le voci SRS in una scheda della finestra principale")
        else:
            self.window_button.setIcon(icon("mdi6.open-in-new"))
            self.window_button.setText("Apri in altra finestra")
            self.window_button.setToolTip("Stacca le voci SRS in una finestra separata, da tenere affiancata alle "
                                          "schede (es. su un secondo schermo)")

    def go_to(self, uuid):
        """Navigate to an item from outside the catalogue: its chapter, and without the filters that hide it."""
        element = self.project.model.get(uuid)
        if element is None:
            return
        if not self.isVisible():
            self._go_to_later = uuid
            return
        chapter = chapter_of(element)
        if self.chapter is not None and chapter != self.chapter:
            index = next((i for i in range(self.tabs.count()) if self.tabs.tabData(i) == chapter), 0)
            self.tabs.setCurrentIndex(index)
        if all(e.uuid != uuid for e in self.model.elements):
            for widget in (self.search, self.show_headings, self.scope, *self.category_boxes.values()):
                widget.blockSignals(True)
            self.search.clear()
            self.show_headings.setChecked(True)
            self.scope.setCurrentIndex(0)  # all the requirements
            self.scope_pick.setVisible(False)
            self.scope_note.setVisible(False)
            for box in self.category_boxes.values():
                box.setChecked(True)
            for widget in (self.search, self.show_headings, self.scope, *self.category_boxes.values()):
                widget.blockSignals(False)
            self.refresh()
        self.reveal(uuid)

    def reveal(self, uuid):
        """Select and show an item (e.g. when coming back from its page); keeps filters and position."""
        row = next((i for i, e in enumerate(self.model.elements) if e.uuid == uuid), None)
        if row is None:
            return
        index = self.model.index(row)
        self.view.setCurrentIndex(index)
        self.view.scrollTo(index, QAbstractItemView.PositionAtCenter)
        self.view.setFocus()

    # --- allocation from the rows --------------------------------------------------------------------

    def _rebuild_links(self):
        """What the rows show: system functions tracing each item directly, derived requirements of each item; the
        roles of the functions in the SA-3 register of each item (primary, secondary)."""
        roles = {}
        for record in self.project.model.of_kind("trace_record"):
            item = record.get("requirement")
            for f in record.get("primary_functions") or []:
                roles[(item, f)] = "funzione primaria"
            for f in record.get("secondary_functions") or []:
                roles.setdefault((item, f), "funzione secondaria")
        self._roles = roles
        functions, derived = {}, {}
        for sf in self.project.model.of_kind("system_function"):
            for uuid in sf.get("sections") or []:
                functions.setdefault(uuid, []).append(sf)
        for d in self.project.model.of_kind("derived_requirement"):
            if d.get("parent"):
                derived.setdefault(d.get("parent"), []).append(d)
        from arcadia_tool.model.srs_links import links_of
        incoming = {}  # the links to each item from the others (see model.srs_links)
        for e in self.project.model.of_kind("requirement"):
            for link_type, target in links_of(e):
                incoming.setdefault(target, []).append((link_type, e))
        self._links = {"functions": functions, "derived": derived, "incoming": incoming}
        self._marks = marks_by_requirement(self.project.model)

    def _analysis(self, element):
        """The button «Analizzato» of a clause: (label, style, who has analysed it). «Non analizzato» if nobody has;
        with more than one person, how many."""
        marks = self._marks.get(element.uuid, [])
        if not marks:
            return "Non analizzato", "none", "Nessuno ha ancora analizzato questa clausola.\nClic: la segni come " \
                                               "analizzata da te."
        user = self.user_of()
        mine = any(is_mine(m, user) for m in marks)
        label = "Analizzato" if len(marks) == 1 else f"Analizzato ({len(marks)})"
        click = "Clic: togli il tuo segno." if mine else "Clic: la segni come analizzata anche da te."
        people = "1 persona" if len(marks) == 1 else f"{len(marks)} persone"
        return label, "mine" if mine else "others", (f"Analizzata da {people}:\n{who_text(self.project.model, marks)}"
                                                    f"\n\n{click}")

    def toggle_analysis(self, item):
        """«Analizzato» clicked: the mark of the user added or taken back, and saved at once (only it)."""
        from arcadia_tool.ui.busy import save_project

        user = self.user_of()
        denied = mark_denied(self.project.model, user)
        if denied:
            QMessageBox.information(self, "Analizzato", denied)
            return
        changed, _marked = toggle(self.project, item, user)
        save_project(self, self.project, changed)
        self._marks = marks_by_requirement(self.project.model)
        self.view.viewport().update()
        self.analysis_changed.emit()

    def _domain(self, uuid):
        """A domain as the rows name it: code and name («DF03 - Movement Authority Management»)."""
        e = self.project.model.get(uuid)
        if e is None:
            return "?"
        return " - ".join(t for t in (e.get("id"), e.get("name")) if t) or self.project.model.label(e)

    def _domain_badges(self, element):
        """The domains of a section as badges: [(«DF03 - Movement Authority Management», principal)]."""
        badges = [(self._domain(element.get("primary_domain")), True)] if element.get("primary_domain") else []
        return badges + [(self._domain(d), False) for d in element.get("contributing_domains") or []]

    def _link_badges(self, element):
        """The badges of a clause (or of a list item): the system functions mapped to it («SF-DF02-03 - Determinare
        la posizione del treno»), those mapped to its section or clause (grey), its derived requirements (purple)."""
        functions = self._links.get("functions", {})

        def named(f):
            return " - ".join(t for t in (f.get("id"), f.get("name")) if t) or f.label

        model, ident = self.project.model, element.get("id") or ""

        def role(f):
            found = getattr(self, "_roles", {}).get((element.uuid, f.uuid))
            return f"\nNel registro SA-3 della voce: {found}." if found else ""

        direct = [(f, None) for f in functions.get(element.uuid, [])]
        inherited, parent = [], element.get("parent")
        while parent:  # functions tracing a section (or a clause) that contains it
            seen = [f for f, _p in direct + inherited]
            inherited += [(f, parent) for f in functions.get(parent, []) if f not in seen]
            parent = self.parents.get(parent)

        def where(uuid):
            part = model.get(uuid)
            kind = "sezione" if part is not None and part.get("item_type") == "Sezione" else "clausola"
            return f"{kind} {part.get('id') if part is not None else '?'}"

        derived = self._links.get("derived", {}).get(element.uuid, [])
        from arcadia_tool.model.srs_links import INVERSE, links_of

        def item_id(uuid):
            target = model.get(uuid)
            return target.get("id") if target is not None else "?"
        links = [(f"→ {item_id(u)}", "link", f"{t} la voce {item_id(u)} (Collega… per cambiarlo).")
                 for t, u in links_of(element)]
        links += [(f"← {source.get('id') or '?'}", "link", f"{INVERSE[t]} {source.get('id') or '?'}.")
                  for t, source in self._links.get("incoming", {}).get(element.uuid, [])]
        return ([(named(f), "function", f"Mappata direttamente alla clausola {ident}.{role(f)}") for f, _p in direct]
                + [(named(f), "inherited", f"Mappata alla {where(p)}, che contiene la voce {ident}: la voce la eredita."
                    f"{role(f)}") for f, p in inherited]
                + [(d.get("id") or "?", "derived", f"Requisito derivato (SA-4) dalla voce {ident}.") for d in derived]
                + links)

    def _links_text(self, element):
        kind = row_kind(element)
        if kind == "section":
            parts = []
            if element.get("primary_domain"):
                parts.append(f"{self._domain(element.get('primary_domain'))} (principale)")
            parts += [f"{self._domain(d)} (contributo)" for d in element.get("contributing_domains") or []]
            return "Domini: " + " · ".join(parts) if parts else "Nessun dominio allocato"
        if kind in ("clause", "item"):
            functions = self._links.get("functions", {})
            direct = [f.get("id") or f.label for f in functions.get(element.uuid, [])]
            inherited = []
            parent = element.get("parent")
            while parent:  # functions tracing a section (or a clause) that contains it
                inherited += [f.get("id") or f.label for f in functions.get(parent, []) if
                              (f.get("id") or f.label) not in direct + inherited]
                parent = self.parents.get(parent)
            parts = direct + [f"{i} (sezione)" for i in inherited]
            text = "Funzioni: " + " · ".join(parts) if parts else "Nessuna funzione di sistema"
            derived = [d.get("id") or "?" for d in self._links.get("derived", {}).get(element.uuid, [])]
            if derived:
                text += "   ·   Derivati: " + ", ".join(derived)
            return text
        return ""

    def run_action(self, uuid, name):
        """«Domini…» of a section, «Mappa a Funzione», «Deriva…», «Condividi» or «Escludi» of a clause."""
        from arcadia_tool.ui.srs_row_actions import DeriveDialog, ItemDomainsDialog, choose_functions

        item = self.project.model.get(uuid)
        if item is None:
            return
        if name == "domains":
            reason = self.edit_mode.reason()  # it changes the item itself
            if reason:
                QMessageBox.information(self, "Solo la Design Authority", reason)
                return
            dialog = ItemDomainsDialog(self.project, item, self)
            if not dialog.exec():
                return
            changed = self.project.allocate_item(item, *dialog.chosen())
        elif name == "functions":
            chosen = choose_functions(self.project, item, self)
            if chosen is None:
                return
            changed = self.project.trace_item_to_functions(item, chosen)
        elif name == ANALYZED:
            self.toggle_analysis(item)
            return
        elif name == "links":  # the other SRS items it refers to, includes or depends on
            from arcadia_tool.ui.srs_links import edit_links
            changed = edit_links(self.project, item, self)
            if not changed:
                return
        elif name in ("share", "exclude"):  # an ADR for the clause, created and opened by the window
            from arcadia_tool.ui.model_tree import SHARED_CLAUSES, UNMAPPED_CLAUSES
            self.clause_declared.emit(SHARED_CLAUSES if name == "share" else UNMAPPED_CLAUSES, uuid)
            return
        elif name == "derive":
            dialog = DeriveDialog(self.project, item, self)
            if not dialog.exec():
                return
            self._rebuild_links()
            self.view.viewport().update()
            self.elements_changed.emit([*dialog.changed])
            self.elements_created.emit()
            return
        else:
            return
        self._rebuild_links()
        self.view.viewport().update()
        if changed:
            self.elements_changed.emit(changed)

    def links_changed(self):
        """The links between SRS items changed elsewhere (e.g. from the model tree): the badges of the rows follow."""
        self._rebuild_links()
        self.view.viewport().update()

    def _double_clicked(self, index):
        pos = self.view.viewport().mapFromGlobal(QCursor.pos())
        if self.delegate.button_at(index, pos) is None:  # a double click on a button is not «open the item»
            self.open_element.emit(index.data(ELEMENT_ROLE).uuid)

    def element_changed(self, element):
        """An item was edited elsewhere (e.g. in the editor): re-measure and repaint it. A function, a derived
        requirement or a domain changed: the rows that show it are repainted."""
        if element.kind in ("system_function", "derived_requirement", "domain"):
            self._rebuild_links()
            self.view.viewport().update()
            return
        if element.kind != "requirement":
            return
        self.view.itemDelegate().invalidate(element.uuid)
        row = next((i for i, e in enumerate(self.model.elements) if e.uuid == element.uuid), None)
        if row is not None:
            index = self.model.index(row)
            self.model.dataChanged.emit(index, index)
            self.view.scheduleDelayedItemsLayout()

    # --- selection and deletion ---------------------------------------------------------------------

    def selected_elements(self):
        return [i.data(ELEMENT_ROLE) for i in sorted(self.view.selectionModel().selectedRows(), key=lambda i: i.row())]

    def _selection_changed(self, *_):
        n = len(self.view.selectionModel().selectedRows())
        self.delete_button.setEnabled(n > 0 and self.edit_mode.enabled)
        self.delete_button.setText(f"Elimina selezionate ({n})" if n else "Elimina selezionate")
        self.delete_button.setToolTip("" if self.edit_mode.enabled else
                                      "Attiva la modalità modifica per eliminare le voci SRS.")

    def context_menu(self, element):
        menu = QMenu(self)
        label = element.get("id") or ""
        menu.addAction(icon("mdi6.arrow-right-bold-box-outline"), f"Vai alla voce {label}",
                       lambda _=False: self.open_element.emit(element.uuid))
        kind = row_kind(element)
        if kind in ("clause", "item"):  # not from chapters and sections
            menu.addAction(icon("mdi6.call-split"), f"Deriva requisito da {label}…",
                           lambda _=False: self.derive_requested.emit(element.uuid))
        if kind:
            menu.addSeparator()
        if kind == "section":
            menu.addAction(icon("mdi6.sitemap-outline"), "Alloca ai domini funzionali…",
                           lambda _=False: self.run_action(element.uuid, "domains")
                           ).setEnabled(not self.edit_mode.reason())
        elif kind in ("clause", "item"):
            if kind == "clause":
                menu.addAction(icon("mdi6.function-variant"), "Alloca alle funzioni di sistema…",
                               lambda _=False: self.run_action(element.uuid, "functions"))
            menu.addAction(icon("mdi6.call-split"), "Deriva più requisiti…",
                           lambda _=False: self.run_action(element.uuid, "derive"))
            menu.addAction(icon("mdi6.link-variant"), "Collega…",
                           lambda _=False: self.run_action(element.uuid, "links"))
        menu.addSeparator()
        n = len(self.view.selectionModel().selectedRows())
        delete = menu.addAction(icon("mdi6.trash-can-outline"), f"Elimina selezionate ({n})",
                                lambda _=False: self.delete_selected())
        delete.setEnabled(self.edit_mode.enabled)
        if not self.edit_mode.enabled:
            delete.setText(f"{delete.text()} – attiva la modalità modifica")
        return menu

    def _context_menu(self, pos):
        index = self.view.indexAt(pos)
        if not index.isValid():
            return
        if not self.view.selectionModel().isSelected(index):
            self.view.setCurrentIndex(index)  # right click outside the selection: act on that item
        self.context_menu(index.data(ELEMENT_ROLE)).exec(self.view.viewport().mapToGlobal(pos))

    def show_coverage(self):
        """«Report di copertura…»: a window of its own, not modal (a double click on an item opens it). While it is
        generated, a window with a loading bar."""
        loading = QProgressDialog("Generazione del report di copertura…", None, 0, 0, self)
        loading.setWindowTitle("Report di copertura")
        loading.setWindowModality(Qt.WindowModal)
        loading.setMinimumDuration(0)
        loading.setAutoClose(False)
        loading.setAutoReset(False)
        loading.setMinimumWidth(420)
        loading.show()
        QApplication.processEvents()

        def progress(done, total, what):
            loading.setLabelText(what)
            loading.setMaximum(total)
            loading.setValue(done)
            QApplication.processEvents()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            dialog = _coverage_dialog_class()(self.project, lambda uuid: self.open_element.emit(uuid), self,
                                              progress=progress)
        finally:
            QApplication.restoreOverrideCursor()
            loading.close()
            loading.deleteLater()
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        self.coverage = dialog
        dialog.show()
        return dialog

    def delete_selected(self):
        selected = self.selected_elements()
        if not selected or not self.edit_mode.enabled:
            return
        if confirm_delete(self, self.project, [e.uuid for e in selected]):
            self.elements_deleted.emit()


def _coverage_dialog_class():
    from arcadia_tool.ui.coverage_report import CoverageReportDialog
    return CoverageReportDialog


class SrsReaderWindow(QWidget):
    """Separate window of the SRS catalogue («Apri in altra finestra»). Closing it closes the catalogue, as
    closing its tab does."""
    closed = Signal()

    def __init__(self, reader, title, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle(title)
        self.resize(1200, 860)
        self.reader = reader
        self.releasing = False  # set when the catalogue goes back to a tab: closing is not closing it
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(reader)
        reader.show()  # hidden by the tab widget it was taken from

    def release(self):
        """Give the catalogue back (to a tab) and close the window."""
        self.releasing = True
        self.layout().removeWidget(self.reader)
        self.reader.setParent(None)
        self.close()
        return self.reader

    def closeEvent(self, event):
        super().closeEvent(event)
        if not self.releasing:
            self.closed.emit()


def confirm_delete(parent, project, uuids, what=None):
    """Ask before deleting SRS items (and the items they contain); returns True if deleted."""
    model = project.model
    targets = model.descendants(uuids)
    contained = len(targets) - len(set(uuids))
    references = model.referencing(targets)
    message = what or f"Eliminare {len(set(uuids))} voci SRS selezionate?"
    details = []
    if contained:
        details.append(f"Verranno eliminate anche {contained} voci contenute (sotto-voci, righe di tabella).")
    if references:
        details.append(f"{len(references)} elementi del modello (es. esiti di tracciatura, funzioni) fanno "
                       "riferimento a queste voci: i riferimenti resteranno senza destinazione.")
    details.append("L'eliminazione diventa definitiva solo al salvataggio; puoi sempre reimportare le voci.")
    box = QMessageBox(QMessageBox.Warning, "Elimina voci SRS", message, QMessageBox.Yes | QMessageBox.Cancel, parent)
    box.setInformativeText("\n\n".join(details))
    box.button(QMessageBox.Yes).setText(f"Elimina {len(targets)} voci")
    box.setDefaultButton(QMessageBox.Cancel)
    if box.exec() != QMessageBox.Yes:
        return False
    project.delete_elements(targets)
    return True
