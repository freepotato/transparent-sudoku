"""Killer Sudoku board widget with transparent background support."""

from itertools import combinations
from typing import List, Optional, Set, Tuple

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from puzzle_fetcher import KillerSudokuPuzzle


class KillerSudokuBoard(QWidget):
    """Custom widget that draws a Killer Sudoku puzzle board."""

    # Signal emitted when a cell is clicked: (row, col)
    cell_clicked = Signal(int, int)
    # Signal emitted when a value is entered on the selected cell
    value_entered = Signal(int, int, int)  # row, col, value (0=clear)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._puzzle: Optional[KillerSudokuPuzzle] = None
        self._user_values: List[List[int]] = []  # user-entered values (0=empty)
        self._pencils: List[List[Set[int]]] = []  # per-cell candidate digits
        self._selected_cells: List[Tuple[int, int]] = []  # drag-selectable cells
        self._anchor_cell: Optional[Tuple[int, int]] = None  # cursor cell
        self._dragging = False
        self._fixed_mask: List[List[bool]] = []  # True for given cells
        self._sum_cells: Set[Tuple[int, int]] = set()  # cells holding a cage sum

        # Typing session: a single digit commits; more digits on the same
        # selection become pencil marks. Only a selection change resets it.
        self._typing_key = None
        self._typing_digits: List[int] = []

        # Undo history for committed values only (pencil marks are not recorded)
        self._undo_stack: List[List[Tuple[int, int, int]]] = []

        # Cage combination panel pagination
        self._combo_page = 0
        self._combo_pages = 0
        self._combo_sig = None

        # Visual settings
        self._bg_color = QColor(0, 0, 0, 0)  # fully transparent bg
        self._cage_border_color = QColor(165, 165, 165, 190)
        self._cage_border_width = 1.0

        # Cell grid: only the 3x3 block separators and the outer frame are solid
        self._block_color = QColor(110, 110, 110, 165)
        self._block_width = 1.0
        self._cage_dash_pattern = [4, 3]
        self._number_color = QColor(20, 20, 20, 255)
        self._fixed_number_color = QColor(20, 20, 20, 255)
        self._pencil_color = QColor(110, 110, 110, 200)
        self._pencil_font_frac = 0.24
        self._cage_sum_color = QColor(160, 160, 160, 210)
        self._selected_color = QColor(100, 150, 255, 100)
        self._highlight_color = QColor(200, 220, 255, 60)
        self._same_digit_color = QColor(255, 200, 80, 75)
        self._cell_size = 40  # base cell size
        self._cage_sum_font_scale = 0.22
        self._number_font_scale = 0.55
        self._fixed_bold = True

        # Allow focus for keyboard input
        self.setFocusPolicy(Qt.StrongFocus)

        # Transparency support
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    # ---- Public API ----

    def set_puzzle(self, puzzle: KillerSudokuPuzzle):
        """Load a new puzzle."""
        self._puzzle = puzzle
        size = puzzle.size
        self._user_values = [[0] * size for _ in range(size)]
        self._pencils = [[set() for _ in range(size)] for _ in range(size)]
        self._fixed_mask = [[puzzle.cells[r][c] != 0 for c in range(size)] for r in range(size)]
        self._selected_cells = []
        self._anchor_cell = None
        self._undo_stack.clear()
        self._end_typing_session()
        self._sum_cells = self._compute_sum_cells()
        self.update()

    def _compute_sum_cells(self) -> Set[Tuple[int, int]]:
        """Cells that show a cage total (top-left of each cage)."""
        if self._puzzle is None:
            return set()
        return {min(cage.cells) for cage in self._puzzle.cages if cage.cells}

    def set_background_color(self, color: QColor):
        self._bg_color = color
        self.update()

    def set_cage_border_color(self, color: QColor):
        self._cage_border_color = color
        self.update()

    def set_number_color(self, color: QColor):
        self._number_color = color
        self._fixed_number_color = color
        self.update()

    def set_cage_sum_color(self, color: QColor):
        self._cage_sum_color = color
        self.update()

    def set_cell_size(self, size: int):
        self._cell_size = max(20, size)
        self.updateGeometry()
        self.update()

    def set_font_scale(self, number_scale: float = 0.55, cage_sum_scale: float = 0.35):
        self._number_font_scale = number_scale
        self._cage_sum_font_scale = cage_sum_scale
        self.update()

    def user_value(self, row: int, col: int) -> int:
        """Get the current value at a cell (fixed or user-entered)."""
        if self._fixed_mask[row][col]:
            return self._puzzle.cells[row][col]
        return self._user_values[row][col]

    def set_user_value(self, row: int, col: int, value: int):
        if self._fixed_mask[row][col]:
            return
        self._user_values[row][col] = value
        self._pencils[row][col].clear()
        self.update()

    def set_pencils(self, row: int, col: int, digits: Set[int]):
        """Mark a cell with pencil candidates (clears any committed value)."""
        if self._fixed_mask[row][col]:
            return
        self._user_values[row][col] = 0
        self._pencils[row][col] = set(digits)
        self.update()

    def pencils(self, row: int, col: int) -> Set[int]:
        return set(self._pencils[row][col]) if self._pencils else set()

    def clear_user_values(self):
        if self._puzzle:
            size = self._puzzle.size
            self._user_values = [[0] * size for _ in range(size)]
            self._pencils = [[set() for _ in range(size)] for _ in range(size)]
            self._undo_stack.clear()
            self._end_typing_session()
            self.update()

    def undo(self) -> bool:
        """Undo the last committed value entry (pencil marks are not tracked)."""
        if not self._undo_stack:
            return False
        group = self._undo_stack.pop()
        for r, c, previous in group:
            self._user_values[r][c] = previous
            self._pencils[r][c].clear()
        self._end_typing_session()
        self.update()
        return True

    def push_undo(self, changes: List[Tuple[int, int, int]]):
        if changes:
            self._undo_stack.append(changes)

    def check_board(self) -> Tuple[int, int, int]:
        """Validate entries against the solution and report only counts.

        Nothing is drawn or coloured: the caller decides how to surface the
        result. Returns (wrong cells, filled cells, editable cells).
        """
        if self._puzzle is None:
            return (0, 0, 0)

        n = self._puzzle.size
        solution = self._puzzle.solution
        wrong = filled = total = 0

        for r in range(n):
            for c in range(n):
                if self._fixed_mask[r][c]:
                    continue
                total += 1
                value = self._user_values[r][c]
                if not value:
                    continue
                filled += 1
                if solution is not None:
                    if solution[r][c] != value:
                        wrong += 1
                elif self._has_conflict(r, c, value):
                    wrong += 1

        return (wrong, filled, total)

    def _has_conflict(self, row: int, col: int, value: int) -> bool:
        """Rule-based fallback when no solution is embedded in the page."""
        n = self._puzzle.size
        for c2 in range(n):
            if c2 != col and self.user_value(row, c2) == value:
                return True
        for r2 in range(n):
            if r2 != row and self.user_value(r2, col) == value:
                return True
        nr = self._puzzle.num_rows_nonet
        nc = self._puzzle.num_cols_nonet
        br, bc = (row // nr) * nr, (col // nc) * nc
        for r2 in range(br, br + nr):
            for c2 in range(bc, bc + nc):
                if (r2, c2) != (row, col) and self.user_value(r2, c2) == value:
                    return True
        for r2, c2 in self._puzzle.cages[self._puzzle.cage_grid[row][col]].cells:
            if (r2, c2) != (row, col) and self.user_value(r2, c2) == value:
                return True
        return False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    # ---- Painting ----

    def sizeHint(self):
        if self._puzzle is None:
            return super().sizeHint()
        n = self._puzzle.size
        return QSize(self._cell_size * n + 2, self._cell_size * n + 2)

    def paintEvent(self, event):
        if self._puzzle is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect()
        n = self._puzzle.size

        # Calculate board size to fit widget, keeping square cells
        side = min(rect.width(), rect.height())
        cell = side / n
        offset_x = (rect.width() - side) / 2
        offset_y = (rect.height() - side) / 2

        # Draw background
        painter.fillRect(rect, self._bg_color)

        # Draw selection highlight first (so grid/cages appear over it)
        for r, c in self._selected_cells:
            sel_rect = QRectF(offset_x + c * cell, offset_y + r * cell, cell, cell)
            painter.fillRect(sel_rect, self._selected_color)

        # Highlight every cell that holds the same digit as the cursor cell
        anchor_value = self.user_value(*self._anchor_cell) if self._anchor_cell else 0
        if anchor_value:
            for r in range(n):
                for c in range(n):
                    if self.user_value(r, c) == anchor_value and (r, c) not in self._selected_cells:
                        cr = QRectF(offset_x + c * cell, offset_y + r * cell, cell, cell)
                        painter.fillRect(cr, self._same_digit_color)

        # Draw cage highlights (same cage as the cursor cell)
        if self._anchor_cell is not None:
            sel_cage = self._puzzle.cage_grid[self._anchor_cell[0]][self._anchor_cell[1]]
            for r in range(n):
                for c in range(n):
                    if self._puzzle.cage_grid[r][c] == sel_cage and (r, c) != self._anchor_cell:
                        cr = QRectF(offset_x + c * cell, offset_y + r * cell, cell, cell)
                        painter.fillRect(cr, self._highlight_color)

        # Dashed cage borders first, solid block lines on top: the two line
        # styles never share a pixel, so the solids always stay crisp.
        self._draw_cage_borders(painter, offset_x, offset_y, cell)
        self._draw_grid(painter, offset_x, offset_y, cell)

        # Draw cage sums
        self._draw_cage_sums(painter, offset_x, offset_y, cell)

        # Draw numbers
        self._draw_numbers(painter, offset_x, offset_y, cell)

        # Single cage selected: list the possible digit combinations
        self._draw_cage_combinations(painter, offset_x, offset_y, cell)

        # Several cages selected: show their combined target
        self._draw_selection_sum(painter, offset_x, offset_y, cell)

    def _complete_cages(self):
        """Return the cages fully covered by the selection, or [] if it is partial."""
        if self._puzzle is None or not self._selected_cells:
            return []
        selected = set(self._selected_cells)
        cages = []
        for cage_id in {self._puzzle.cage_grid[r][c] for r, c in self._selected_cells}:
            cage = self._puzzle.cages[cage_id]
            if not set(cage.cells).issubset(selected):
                return []
            cages.append(cage)
        if sum(len(c.cells) for c in cages) != len(selected):
            return []
        return sorted(cages, key=lambda c: c.index)

    def _draw_selection_sum(self, painter, ox, oy, cell):
        """Show the sum of cage totals when several whole cages are selected."""
        cages = self._complete_cages()
        if len(cages) < 2:
            return

        total = sum(c.sum_value for c in cages)
        text = f"Σ {total} · {len(cages)} cages"

        font = QFont()
        font.setPointSizeF(max(8.0, cell * 0.22))
        painter.setFont(font)
        metrics = QFontMetrics(font)

        pad_x, pad_y = 6.0, 3.0
        box_w = metrics.horizontalAdvance(text) + pad_x * 2
        box_h = metrics.height() + pad_y * 2

        cols = [c for _, c in self._selected_cells]
        rows = [r for r, _ in self._selected_cells]
        left = ox + min(cols) * cell
        right = ox + (max(cols) + 1) * cell
        top = oy + min(rows) * cell
        bottom = oy + (max(rows) + 1) * cell

        board_left = ox
        board_right = ox + self._puzzle.size * cell

        # Prefer the right side of the selection, fall back to the left
        if right + 4 + box_w <= board_right:
            box_x = right + 4
        elif left - 4 - box_w >= board_left:
            box_x = left - 4 - box_w
        else:
            box_x = max(board_left, board_right - box_w)

        box_y = top - box_h - 3
        if box_y < oy:
            box_y = bottom + 3
        if box_y + box_h > oy + self._puzzle.size * cell:
            box_y = max(oy, top + 3)

        pill = QRectF(box_x, box_y, box_w, box_h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(70, 70, 70, 150))
        painter.drawRoundedRect(pill, 4, 4)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(245, 245, 245, 210))
        painter.drawText(pill, Qt.AlignCenter, text)

    def _draw_cage_combinations(self, painter, ox, oy, cell):
        """List every digit combination that still fits the selected cage.

        Drawn as a tiny box in the bottom-left corner of the board.
        """
        self._combo_pages = 0

        cages = self._complete_cages()
        if len(cages) != 1:
            return

        cage = cages[0]
        lines = self._cage_combination_lines(cage)

        font = QFont()
        font.setPointSizeF(max(5.0, cell * 0.19))
        painter.setFont(font)
        metrics = QFontMetrics(font)

        per_page = 4
        pages = max(1, (len(lines) + per_page - 1) // per_page)

        signature = (cage.index, tuple(sorted(self._selected_cells)), tuple(lines))
        if signature != self._combo_sig:
            self._combo_sig = signature
            self._combo_page = 0
        self._combo_page = min(self._combo_page, pages - 1)
        self._combo_pages = pages

        page = self._combo_page
        shown = lines[page * per_page:(page + 1) * per_page]

        line_h = metrics.height() + 1
        pad_x, pad_y = 6, 4

        text_w = max(metrics.horizontalAdvance(t) for t in shown)
        box_w = text_w + pad_x * 2
        box_h = line_h * len(shown) + pad_y * 2

        n = self._puzzle.size
        box_x = ox + 3
        box_y = oy + n * cell - box_h - 3

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 30, 30, 140))
        painter.drawRoundedRect(QRectF(box_x, box_y, box_w, box_h), 3, 3)
        painter.setBrush(Qt.NoBrush)

        # Combination lines
        painter.setFont(font)
        painter.setPen(QColor(240, 240, 240, 225))
        y = box_y + pad_y + metrics.ascent()
        for line in shown:
            painter.drawText(QPointF(box_x + pad_x, y), line)
            y += line_h

    def _draw_pencils(self, painter, r, c, ox, oy, cell, digits):
        """Pencil marks as a queue of digits with a fixed size.

        Digits flow left to right and wrap at the cell padding, like the
        website's pencil marks.
        """
        font = QFont()
        font.setPixelSize(max(5, int(cell * self._pencil_font_frac)))
        painter.setFont(font)
        painter.setPen(self._pencil_color)

        metrics = QFontMetrics(font)
        spacing = max(1, int(font.pixelSize() * 0.08))
        pad_x = max(2, int(cell * 0.07))
        avail_w = cell - pad_x * 2

        # Keep the cage sum readable in top-left cells
        top_pad = cell * 0.26 if (r, c) in self._sum_cells else pad_x * 0.5

        lines: List[List[str]] = [[]]
        line_w = 0
        for d in sorted(digits):
            glyph = str(d)
            w = metrics.horizontalAdvance(glyph)
            if lines[-1] and line_w + spacing + w > avail_w:
                lines.append([])
                line_w = 0
            if lines[-1]:
                line_w += spacing
            lines[-1].append(glyph)
            line_w += w

        x0 = ox + c * cell + pad_x
        y = oy + r * cell + top_pad + metrics.ascent()
        for line in lines:
            x = x0
            for glyph in line:
                painter.drawText(QPointF(x, y), glyph)
                x += metrics.horizontalAdvance(glyph) + spacing
            y += metrics.height()

    def _cage_combination_lines(self, cage) -> List[str]:
        """All distinct-digit combinations that still fill the cage."""
        values = [self.user_value(r, c) for r, c in cage.cells]
        used = {v for v in values if v}
        empty = len([v for v in values if not v])
        remaining = cage.sum_value - sum(used)

        if empty == 0:
            return ["✓" if remaining == 0 else f"✗ {remaining:+d}"]
        if remaining <= 0:
            return ["✗"]

        digits = [d for d in range(1, 10) if d not in used]
        combos = [c for c in combinations(digits, empty) if sum(c) == remaining]
        return [" ".join(str(d) for d in combo) for combo in combos] or ["—"]

    def _draw_grid(self, painter, ox, oy, cell):
        """Solid lines: the outer frame and the 3x3 block separators only.

        No thin lines between individual cells. Cell divisions come from the
        dashed cage borders, exactly like the reference board, so solid and
        dashed lines never overlap.
        """
        if self._puzzle is None:
            return
        n = self._puzzle.size
        block_rows = self._puzzle.num_rows_nonet or 3
        block_cols = self._puzzle.num_cols_nonet or 3
        side = n * cell

        thick = QPen(self._block_color, self._block_width)
        thick.setCapStyle(Qt.FlatCap)
        painter.setPen(thick)
        painter.setBrush(Qt.NoBrush)

        # Half-pixel alignment keeps 1px strokes crisp instead of blurring
        # across two pixels.
        for r in range(1, n):
            if r % block_rows:
                continue
            y = oy + r * cell + 0.5
            painter.drawLine(QPointF(ox, y), QPointF(ox + side, y))

        for c in range(1, n):
            if c % block_cols:
                continue
            x = ox + c * cell + 0.5
            painter.drawLine(QPointF(x, oy), QPointF(x, oy + side))

        # Outer frame: keep the whole stroke inside the widget so it is not
        # clipped in half by the board edge.
        painter.drawRect(QRectF(ox + 0.5, oy + 0.5, side - 1.0, side - 1.0))

    def _draw_cage_borders(self, painter, ox, oy, cell):
        """Dashed cage borders.

        Drawn only on plain cell edges: edges that sit on a 3x3 block boundary
        or on the outer frame are already covered by the solid lines, so a
        dash never lands on top of a solid stroke.
        """
        if self._puzzle is None:
            return

        pen = QPen(self._cage_border_color, self._cage_border_width)
        pen.setCapStyle(Qt.FlatCap)
        pen.setDashPattern(self._cage_dash_pattern)
        painter.setPen(pen)

        h_runs, v_runs = self._cage_border_runs()

        # Half-pixel alignment matches the solid lines, so a dash stays crisp
        # and stops cleanly at a block separator instead of bleeding into it.
        for r, spans in h_runs.items():
            y = oy + r * cell + 0.5
            for c0, c1 in spans:
                painter.drawLine(QPointF(ox + c0 * cell, y),
                                 QPointF(ox + c1 * cell, y))

        for c, spans in v_runs.items():
            x = ox + c * cell + 0.5
            for r0, r1 in spans:
                painter.drawLine(QPointF(x, oy + r0 * cell),
                                 QPointF(x, oy + r1 * cell))

    def _cage_border_runs(self):
        """Cage edges grouped into continuous runs.

        Collinear edges of neighbouring cells are merged so one dash sequence
        spans the whole side instead of restarting at every cell corner.
        """
        n = self._puzzle.size
        block_rows = self._puzzle.num_rows_nonet or 3
        block_cols = self._puzzle.num_cols_nonet or 3
        grid = self._puzzle.cage_grid

        h_runs = {}
        for r in range(1, n):
            if r % block_rows == 0:
                continue
            edges = [c for c in range(n) if grid[r - 1][c] != grid[r][c]]
            if edges:
                h_runs[r] = self._merge_spans(edges)

        v_runs = {}
        for c in range(1, n):
            if c % block_cols == 0:
                continue
            edges = [r for r in range(n) if grid[r][c - 1] != grid[r][c]]
            if edges:
                v_runs[c] = self._merge_spans(edges)

        return h_runs, v_runs

    @staticmethod
    def _merge_spans(indices):
        """Merge ascending cell indices into [start, end) spans."""
        spans = []
        for i in indices:
            if spans and spans[-1][1] == i:
                spans[-1][1] = i + 1
            else:
                spans.append([i, i + 1])
        return [(s, e) for s, e in spans]

    def _draw_cage_sums(self, painter, ox, oy, cell):
        """Draw cage sum numbers at the top-left of the first cell of each cage."""
        if self._puzzle is None:
            return
        n = self._puzzle.size
        sum_font_size = max(5, int(cell * self._cage_sum_font_scale))
        font = QFont()
        font.setPointSizeF(sum_font_size)
        painter.setFont(font)
        painter.setPen(self._cage_sum_color)

        # Track which cages we've drawn
        drawn_cages = set()
        for r in range(n):
            for c in range(n):
                ci = self._puzzle.cage_grid[r][c]
                if ci in drawn_cages:
                    continue
                drawn_cages.add(ci)

                # Find the top-leftmost cell of this cage
                top_left = None
                for cr in range(n):
                    for cc in range(n):
                        if self._puzzle.cage_grid[cr][cc] == ci:
                            if top_left is None or cr < top_left[0] or (cr == top_left[0] and cc < top_left[1]):
                                top_left = (cr, cc)

                cage = self._puzzle.cages[ci]
                tr, tc = top_left
                tx = ox + tc * cell + 2
                ty = oy + tr * cell + sum_font_size + 1

                sum_text = str(cage.sum_value)

                painter.setPen(self._cage_sum_color)
                painter.drawText(QPointF(tx, ty), sum_text)

    def _draw_numbers(self, painter, ox, oy, cell):
        """Draw committed values and pencil marks."""
        if self._puzzle is None:
            return
        n = self._puzzle.size
        font_size = max(10, int(cell * self._number_font_scale))

        fixed_font = QFont()
        fixed_font.setPointSizeF(font_size)
        if self._fixed_bold:
            fixed_font.setBold(True)

        user_font = QFont()
        user_font.setPointSizeF(font_size)

        for r in range(n):
            for c in range(n):
                val = self.user_value(r, c)

                if val == 0:
                    digits = self._pencils[r][c]
                    if digits:
                        self._draw_pencils(painter, r, c, ox, oy, cell, digits)
                    continue

                if self._fixed_mask[r][c]:
                    painter.setFont(fixed_font)
                    painter.setPen(self._fixed_number_color)
                else:
                    painter.setFont(user_font)
                    painter.setPen(self._number_color)

                text_rect = QRectF(ox + c * cell, oy + r * cell, cell, cell)
                painter.drawText(text_rect, Qt.AlignCenter, str(val))

    # ---- Mouse & Keyboard ----

    def _cell_from_pos(self, pos):
        """Convert widget position to (row, col) cell coordinates."""
        if self._puzzle is None:
            return None
        rect = self.rect()
        n = self._puzzle.size
        side = min(rect.width(), rect.height())
        cell = side / n
        offset_x = (rect.width() - side) / 2
        offset_y = (rect.height() - side) / 2

        x = pos.x() - offset_x
        y = pos.y() - offset_y
        if x < 0 or y < 0 or x >= side or y >= side:
            return None
        col = int(x / cell)
        row = int(y / cell)
        if 0 <= row < n and 0 <= col < n:
            return (row, col)
        return None

    def wheelEvent(self, event):
        """Scroll through the candidate-combination pages."""
        if self._combo_pages > 1:
            delta = event.angleDelta().y()
            if delta:
                step = -1 if delta > 0 else 1
                page = self._combo_page + step
                self._combo_page = max(0, min(self._combo_pages - 1, page))
                self.update()
                event.accept()
                return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        cell = self._cell_from_pos(event.position())
        if cell is not None:
            if self._selected_cells != [cell]:
                self._end_typing_session()
            self._selected_cells = [cell]
            self._anchor_cell = cell
            self._dragging = True
            self.setFocus()
            self.cell_clicked.emit(cell[0], cell[1])
        else:
            if self._selected_cells:
                self._end_typing_session()
            self._selected_cells = []
            self._anchor_cell = None
        self.update()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            cell = self._cell_from_pos(event.position())
            if cell is not None and cell not in self._selected_cells:
                self._end_typing_session()
                self._selected_cells.append(cell)
                self._anchor_cell = cell
                self.cell_clicked.emit(cell[0], cell[1])
                self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self._anchor_cell is None or self._puzzle is None:
            super().keyPressEvent(event)
            return

        row, col = self._anchor_cell
        key = event.key()

        # Number keys 1-9 (top row and keypad) fill every selected cell
        value = 0
        if Qt.Key_1 <= key <= Qt.Key_9:
            value = key - Qt.Key_0
        elif Qt.Key_0 <= key <= Qt.Key_9:
            value = key - Qt.Key_0

        if value:
            self._type_digit(value)
            event.accept()
            return

        # Delete/Backspace/Clear (also plain 0 on the number row)
        if key in (Qt.Key_Delete, Qt.Key_Backspace, Qt.Key_C, Qt.Key_0):
            if key == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
                super().keyPressEvent(event)
                return
            self._end_typing_session()
            changes = []
            for r, c in self._selected_cells or [(row, col)]:
                changes.append((r, c, self._user_values[r][c]))
                self.set_user_value(r, c, 0)
                self.value_entered.emit(r, c, 0)
            self.push_undo(changes)
            event.accept()
            return

        # Arrow keys
        row_move = 0
        col_move = 0
        if key == Qt.Key_Up:
            row_move = -1
        elif key == Qt.Key_Down:
            row_move = 1
        elif key == Qt.Key_Left:
            col_move = -1
        elif key == Qt.Key_Right:
            col_move = 1

        if row_move or col_move:
            n = self._puzzle.size
            new_r = (row + row_move) % n
            new_c = (col + col_move) % n
            self._end_typing_session()
            self._anchor_cell = (new_r, new_c)
            self._selected_cells = [self._anchor_cell]
            self.cell_clicked.emit(new_r, new_c)
            self.update()
            event.accept()
            return

        super().keyPressEvent(event)

    def _type_digit(self, digit: int):
        """Commit a lone digit; accumulate several digits into pencil marks."""
        cells = [(r, c) for r, c in (self._selected_cells or [self._anchor_cell])
                 if r is not None and not self._fixed_mask[r][c]]
        if not cells:
            return

        signature = tuple(sorted(cells))
        same_session = self._typing_key == signature

        if same_session:
            if digit not in self._typing_digits:
                self._typing_digits.append(digit)
        else:
            self._typing_digits = [digit]
        self._typing_key = signature

        if len(self._typing_digits) == 1:
            changes = []
            for r, c in cells:
                changes.append((r, c, self._user_values[r][c]))
                self.set_user_value(r, c, digit)
                self.value_entered.emit(r, c, digit)
            self.push_undo(changes)
        else:
            digits = set(self._typing_digits)
            for r, c in cells:
                self.set_pencils(r, c, digits)
                self.value_entered.emit(r, c, 0)

    def _end_typing_session(self):
        self._typing_key = None
        self._typing_digits = []
