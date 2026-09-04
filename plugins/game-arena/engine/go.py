"""Go (Weiqi/Baduk) engine - 9/13/19 board, capture, ko, suicide, scoring."""
from __future__ import annotations
from typing import List, Tuple, Dict, Set, Optional

try:
    from .base import BaseGame
except ImportError:
    from base import BaseGame


class GoGame(BaseGame):
    """Go engine implementing core rules: capture, ko, suicide, pass, scoring."""

    def create_board(self, size: int) -> List[List[int]]:
        return [[0] * size for _ in range(size)]

    def check_win(self, board: List[List[int]], x: int, y: int, color: int):
        # Go has no win-by-placement; win is by scoring after two passes.
        # Keep interface compatible.
        return False, []

    def is_draw(self, board: List[List[int]]) -> bool:
        return False

    # ── helpers ──
    def _in_bounds(self, board: List[List[int]], x: int, y: int) -> bool:
        n = len(board)
        return 0 <= x < n and 0 <= y < n

    def _neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        return [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]

    def _group(self, board: List[List[int]], x: int, y: int) -> Set[Tuple[int, int]]:
        """Flood fill to get all stones of same color connected orthogonally."""
        color = board[y][x]
        if color == 0:
            return set()
        n = len(board)
        visited: Set[Tuple[int, int]] = set()
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue
            if not (0 <= cx < n and 0 <= cy < n):
                continue
            if board[cy][cx] != color:
                continue
            visited.add((cx, cy))
            for nx, ny in self._neighbors(cx, cy):
                if (nx, ny) not in visited and 0 <= nx < n and 0 <= ny < n and board[ny][nx] == color:
                    stack.append((nx, ny))
        return visited

    def _liberties(self, board: List[List[int]], group: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        libs: Set[Tuple[int, int]] = set()
        n = len(board)
        for gx, gy in group:
            for nx, ny in self._neighbors(gx, gy):
                if 0 <= nx < n and 0 <= ny < n and board[ny][nx] == 0:
                    libs.add((nx, ny))
        return libs

    def _captured_groups(self, board: List[List[int]], x: int, y: int, color: int) -> List[Set[Tuple[int, int]]]:
        """After placing at (x,y), find opponent groups with 0 liberties."""
        opp = 2 if color == 1 else 1
        captured: List[Set[Tuple[int, int]]] = []
        seen: Set[Tuple[int, int]] = set()
        for nx, ny in self._neighbors(x, y):
            if not self._in_bounds(board, nx, ny):
                continue
            if board[ny][nx] != opp:
                continue
            if (nx, ny) in seen:
                continue
            grp = self._group(board, nx, ny)
            seen.update(grp)
            if len(self._liberties(board, grp)) == 0:
                captured.append(grp)
        return captured

    def _board_hash(self, board: List[List[int]]) -> str:
        return "".join(str(c) for row in board for c in row)

    # ── public API ──
    def is_legal_move(
        self,
        board: List[List[int]],
        x: int,
        y: int,
        color: int,
        ko: Optional[Tuple[int, int]] = None,
        previous_hash: Optional[str] = None,
    ) -> Tuple[bool, str]:
        n = len(board)
        if not (0 <= x < n and 0 <= y < n):
            return False, f"x,y out of range 0-{n-1}"
        if board[y][x] != 0:
            return False, f"cell ({x},{y}) already occupied"
        if ko is not None and (x, y) == ko:
            return False, f"ko forbidden at ({x},{y}), need to play elsewhere first"

        # Simulate placement
        board[y][x] = color
        captured = self._captured_groups(board, x, y, color)
        # Remove captured temporarily to check suicide
        for grp in captured:
            for gx, gy in grp:
                board[gy][gx] = 0

        # Check suicide: own group must have liberties after capture removal
        own_group = self._group(board, x, y)
        # If we captured, own_group may be empty because we cleared? Actually we placed stone, so group exists
        # Re-add stone if we cleared it incorrectly
        if not own_group:
            # This happens if we removed own stone as part of captured? Should not happen
            own_group = {(x, y)}
        libs = self._liberties(board, own_group)
        if len(libs) == 0 and len(captured) == 0:
            board[y][x] = 0
            # Restore captured
            opp = 2 if color == 1 else 1
            for grp in captured:
                for gx, gy in grp:
                    board[gy][gx] = opp
            return False, "suicide move not allowed (no liberties and no capture)"

        # Restore board for caller (undo simulation)
        board[y][x] = 0
        opp = 2 if color == 1 else 1
        for grp in captured:
            for gx, gy in grp:
                board[gy][gx] = opp

        # Ko superko check via hash if provided
        if previous_hash is not None:
            # Simulate again to get hash
            board[y][x] = color
            for grp in captured:
                for gx, gy in grp:
                    board[gy][gx] = 0
            h = self._board_hash(board)
            board[y][x] = 0
            for grp in captured:
                for gx, gy in grp:
                    board[gy][gx] = opp
            if h == previous_hash:
                return False, "ko/superko violation: board repetition not allowed"

        return True, ""

    def play_move(
        self,
        board: List[List[int]],
        x: int,
        y: int,
        color: int,
        captures: Dict[str, int],
        ko: Optional[Tuple[int, int]],
        history_hashes: List[str],
    ) -> Tuple[bool, str, Optional[Tuple[int, int]], int]:
        """
        Execute move, return (ok, error_msg, new_ko, captured_count).
        Mutates board and captures dict.
        """
        legal, msg = self.is_legal_move(board, x, y, color, ko, history_hashes[-1] if history_hashes else None)
        if not legal:
            return False, msg, ko, 0

        board[y][x] = color
        captured_groups = self._captured_groups(board, x, y, color)
        captured_count = 0
        for grp in captured_groups:
            for gx, gy in grp:
                board[gy][gx] = 0
                captured_count += 1

        # Update captures
        key = "black" if color == 1 else "white"
        captures[key] = captures.get(key, 0) + captured_count

        # Ko detection: if single stone captured and single stone placed, ko point is the captured stone position
        new_ko: Optional[Tuple[int, int]] = None
        if captured_count == 1 and len(captured_groups) == 1 and len(captured_groups[0]) == 1:
            # Check if the placed stone's group is single stone with single liberty (the ko point)
            own_group = self._group(board, x, y)
            if len(own_group) == 1 and len(self._liberties(board, own_group)) == 1:
                # The captured stone position is ko
                cap_pos = next(iter(captured_groups[0]))
                new_ko = cap_pos

        return True, "", new_ko, captured_count

    def score(self, board: List[List[int]], captures: Dict[str, int], komi: float = 6.5) -> Dict:
        """
        Area scoring (Chinese) + komi: stones + territory.
        Returns dict with black_score, white_score, black_territory, white_territory, black_stones, white_stones, winner, margin.
        """
        n = len(board)
        # Count stones
        black_stones = sum(cell == 1 for row in board for cell in row)
        white_stones = sum(cell == 2 for row in board for cell in row)

        # Flood fill empty regions
        visited = [[False] * n for _ in range(n)]
        black_territory = 0
        white_territory = 0
        territory_board = [[0] * n for _ in range(n)]  # 0 neutral, 1 black, 2 white

        for y in range(n):
            for x in range(n):
                if board[y][x] != 0 or visited[y][x]:
                    continue
                # BFS empty region
                region: List[Tuple[int, int]] = []
                border_colors: Set[int] = set()
                stack = [(x, y)]
                visited[y][x] = True
                while stack:
                    cx, cy = stack.pop()
                    region.append((cx, cy))
                    for nx, ny in self._neighbors(cx, cy):
                        if not (0 <= nx < n and 0 <= ny < n):
                            continue
                        if board[ny][nx] == 0 and not visited[ny][nx]:
                            visited[ny][nx] = True
                            stack.append((nx, ny))
                        elif board[ny][nx] == 1:
                            border_colors.add(1)
                        elif board[ny][nx] == 2:
                            border_colors.add(2)
                # Determine owner
                if border_colors == {1}:
                    black_territory += len(region)
                    for rx, ry in region:
                        territory_board[ry][rx] = 1
                elif border_colors == {2}:
                    white_territory += len(region)
                    for rx, ry in region:
                        territory_board[ry][rx] = 2
                else:
                    # dame / neutral
                    pass

        # Area scoring
        black_score = black_stones + black_territory
        white_score = white_stones + white_territory + komi

        # Also show Japanese style (territory + captures) for reference
        black_japanese = black_territory + captures.get("white", 0)
        white_japanese = white_territory + captures.get("black", 0) + komi

        if black_score > white_score:
            winner = "black"
            margin = black_score - white_score
        elif white_score > black_score:
            winner = "white"
            margin = white_score - black_score
        else:
            winner = "draw"
            margin = 0

        return {
            "black_stones": black_stones,
            "white_stones": white_stones,
            "black_territory": black_territory,
            "white_territory": white_territory,
            "black_captures": captures.get("black", 0),
            "white_captures": captures.get("white", 0),
            "komi": komi,
            "black_score": black_score,
            "white_score": white_score,
            "black_japanese": black_japanese,
            "white_japanese": white_japanese,
            "territory_board": territory_board,
            "winner": winner,
            "margin": margin,
            "result": f"{'B' if winner=='black' else 'W' if winner=='white' else 'Draw'}+{margin:.1f}" if winner != "draw" else "Draw",
        }

    def render_ascii(self, board: List[List[int]], last_move=None, ko=None, territory_board=None) -> str:
        n = len(board)
        header = "   " + " ".join(f"{i:2d}" for i in range(n))
        lines = [header]
        for y in range(n):
            row = f"{y:2d} "
            for x in range(n):
                v = board[y][x]
                is_last = last_move and tuple(last_move) == (x, y)
                is_ko = ko and tuple(ko) == (x, y)
                if v == 1:
                    ch = "[●]" if is_last else " ●"
                elif v == 2:
                    ch = "[○]" if is_last else " ○"
                else:
                    if is_ko:
                        ch = " ×"
                    elif territory_board and territory_board[y][x] == 1:
                        ch = " ▪"
                    elif territory_board and territory_board[y][x] == 2:
                        ch = " ▫"
                    else:
                        ch = " ."
                row += ch
            lines.append(row)
        return "\n".join(lines)
