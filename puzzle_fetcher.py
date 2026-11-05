"""Fetch and decode Killer Sudoku puzzles from dailykillersudoku.com."""

import base64
import datetime
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import requests


DKS_PUZZLE_URL = "https://www.dailykillersudoku.com/puzzle/{puzzle_id}"
DKS_BY_DATE_URL = "https://www.dailykillersudoku.com/puzzles/by_date"


@dataclass
class Cage:
    """A cage in a Killer Sudoku puzzle."""
    index: int
    sum_value: int
    cells: List[Tuple[int, int]] = field(default_factory=list)


@dataclass
class KillerSudokuPuzzle:
    """Represents a Killer Sudoku puzzle."""
    puzzle_id: int
    date: str
    difficulty: int
    size: int  # 9 for standard
    num_rows_nonet: int  # nonet dimensions (e.g., 3 for 3x3)
    num_cols_nonet: int
    cells: List[List[int]]  # fixed values (0 = empty)
    cage_grid: List[List[int]]  # cage index per cell
    cages: List[Cage]  # cage info with sums and cells
    puzzle_type: int  # 1=Sudoku, 2=Killer Sudoku, 4=Greater-Than Killer
    solution: Optional[List[List[int]]] = None

    def cell_cage(self, row: int, col: int) -> int:
        return self.cage_grid[row][col]


class DKSFetcher:
    """Fetches puzzles from dailykillersudoku.com."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def fetch_puzzle(self, puzzle_id: int) -> KillerSudokuPuzzle:
        """Fetch a puzzle by its ID number."""
        url = DKS_PUZZLE_URL.format(puzzle_id=puzzle_id)
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        return self._parse_puzzle_page(resp.text)

    def fetch_puzzle_ids_for_date(self, date: datetime.date) -> List[int]:
        """Return the standard Killer Sudoku puzzle IDs published on a date.

        The site renders the daily list through the ``/puzzles/by_date`` endpoint.
        Greater-Than Killer puzzles are listed after the ``#greaterThanPuzzles``
        heading and are intentionally skipped.
        """
        resp = self.session.get(
            DKS_BY_DATE_URL,
            params={"date": date.isoformat()},
            timeout=15,
        )
        resp.raise_for_status()

        html = resp.text
        cutoff = html.find('id="greaterThanPuzzles"')
        if cutoff != -1:
            html = html[:cutoff]

        ids = [int(m) for m in re.findall(r'class="puzzle-number">(\d+)<', html)]
        if not ids:
            # Fall back to any linked puzzle that is not in the Greater-Than section
            ids = [int(m) for m in re.findall(r"/puzzle/(\d+)", html)]
        return list(dict.fromkeys(ids))

    def fetch_today_puzzle_ids(self, days_back: int = 1) -> List[int]:
        """Return today's puzzle IDs, falling back a few days for time zone lag."""
        today = datetime.date.today()
        for offset in range(days_back + 1):
            ids = self.fetch_puzzle_ids_for_date(today - datetime.timedelta(days=offset))
            if ids:
                return ids
        raise ValueError(
            "No puzzle found for today. The site may not have published it yet."
        )

    def _parse_puzzle_page(self, html: str) -> KillerSudokuPuzzle:
        """Extract puzzle data from the page HTML."""
        # Find the JSON config passed to DKS.Puzzle constructor
        # Looks like: new DKS.Puzzle({"id":872,"date":"2009-10-15",...})
        match = re.search(
            r'new\s+DKS\.Puzzle\s*\(\s*(\{[^}]+\})\s*\)',
            html,
            re.DOTALL
        )
        if not match:
            # Try a more greedy match (JSON can contain nested braces...)
            match = re.search(
                r'board_base64["\s:]+["\']([A-Za-z0-9+/=]+)["\']',
                html
            )
            if not match:
                raise ValueError("Could not find puzzle data in page HTML")
            # We need the full JSON object
            json_match = re.search(
                r'(\{[^}]*board_base64["\s:]+["\'][A-Za-z0-9+/=]+["\'][^}]*\})',
                html,
                re.DOTALL
            )
            if not json_match:
                raise ValueError("Could not parse puzzle JSON")
            puzzle_json = json.loads(json_match.group(1))
        else:
            puzzle_json = json.loads(match.group(1))

        board_b64 = puzzle_json["board_base64"]
        solution_b64 = puzzle_json.get("solution_base64")

        board = self._decode_board(board_b64)
        solution = None
        if solution_b64:
            solution = self._decode_solution(solution_b64, board["size"])

        # Build cage objects
        cages_by_index: dict = {}
        for idx, sum_val in enumerate(board["cage_sums"]):
            cages_by_index[idx] = Cage(index=idx, sum_value=sum_val)

        for r in range(board["size"]):
            for c in range(board["size"]):
                ci = board["cage_grid"][r][c]
                cages_by_index[ci].cells.append((r, c))

        return KillerSudokuPuzzle(
            puzzle_id=puzzle_json["id"],
            date=puzzle_json["date"],
            difficulty=puzzle_json["difficulty"],
            size=board["size"],
            num_rows_nonet=board["num_rows_nonet"],
            num_cols_nonet=board["num_cols_nonet"],
            cells=board["cells"],
            cage_grid=board["cage_grid"],
            cages=list(cages_by_index.values()),
            puzzle_type=puzzle_json.get("puzzle_type", 1),
            solution=solution,
        )

    @staticmethod
    def _decode_board(b64: str) -> dict:
        """Decode the board_base64 field.

        Format:
          byte 0: [version_high_nibble:4][puzzle_type:4]
          byte 1: [size:4][num_rows_nonet_minus1:2][num_cols_nonet_minus1:2]
          For each cell (size*size times):
            byte: fixed_value (0 if none)
            byte: cage_index
          For each cage:
            byte: cage_sum
        """
        data = list(base64.b64decode(b64))
        if len(data) < 2:
            raise ValueError("Board data too short")

        version = (data[0] >> 4) & 0xF
        puzzle_type = data[0] & 0xF
        data.pop(0)

        size = (data[0] >> 4) & 0xF
        num_rows_nonet = 1 + ((data[0] >> 2) & 0x3)
        num_cols_nonet = 1 + (data[0] & 0x3)
        data.pop(0)

        cells = [[0] * size for _ in range(size)]
        cage_grid = [[0] * size for _ in range(size)]

        for r in range(size):
            for c in range(size):
                fixed_val = data.pop(0)
                cage_idx = data.pop(0)
                cells[r][c] = fixed_val
                cage_grid[r][c] = cage_idx

        # Collect all cage indices used
        all_cage_indices = set()
        for r in range(size):
            for c in range(size):
                all_cage_indices.add(cage_grid[r][c])
        num_cages = max(all_cage_indices) + 1

        cage_sums = []
        for i in range(num_cages):
            cage_sums.append(data.pop(0))

        return {
            "version": version,
            "puzzle_type": puzzle_type,
            "size": size,
            "num_rows_nonet": num_rows_nonet,
            "num_cols_nonet": num_cols_nonet,
            "cells": cells,
            "cage_grid": cage_grid,
            "cage_sums": cage_sums,
        }

    @staticmethod
    def _decode_solution(b64: str, size: int) -> List[List[int]]:
        """Decode the solution_base64 field.

        Format:
          byte 0: must be 0
          byte 1: same encoding as board byte 1 (size/nonet info)
          For each cell (size*size times): value (1-9)
        """
        data = list(base64.b64decode(b64))
        header = data.pop(0)
        if header != 0:
            raise ValueError(f"Invalid solution header: {header}")
        size_byte = data.pop(0)
        decoded_size = (size_byte >> 4) & 0xF
        if decoded_size != size:
            raise ValueError(f"Solution size mismatch: {decoded_size} vs {size}")

        solution = []
        for r in range(size):
            row = []
            for c in range(size):
                row.append(data.pop(0))
            solution.append(row)
        return solution
