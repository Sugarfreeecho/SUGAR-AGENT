"""Gomoku engine - variable board size 9-19, 5 in a row wins."""
from __future__ import annotations
from typing import List, Tuple
try:
    from .base import BaseGame
except ImportError:
    from base import BaseGame

class GomokuGame(BaseGame):
    def create_board(self, size: int) -> List[List[int]]:
        return [[0]*size for _ in range(size)]

    def check_win(self, board: List[List[int]], x: int, y: int, color: int) -> Tuple[bool, List[Tuple[int,int]]]:
        n = len(board)
        dirs = [(1,0),(0,1),(1,1),(1,-1)]
        for dx, dy in dirs:
            line = [(x,y)]
            # forward
            nx, ny = x+dx, y+dy
            while 0 <= nx < n and 0 <= ny < n and board[ny][nx]==color:
                line.append((nx,ny))
                nx+=dx; ny+=dy
            # backward
            nx, ny = x-dx, y-dy
            while 0 <= nx < n and 0 <= ny < n and board[ny][nx]==color:
                line.insert(0,(nx,ny))
                nx-=dx; ny-=dy
            if len(line) >= 5:
                # return exactly 5 contiguous containing (x,y) - take centered window
                # find index of (x,y)
                idx = line.index((x,y))
                start = max(0, idx-4)
                # ensure 5 length, slide if needed
                if start+5 > len(line):
                    start = len(line)-5
                return True, line[start:start+5]
        return False, []

    def is_draw(self, board: List[List[int]]) -> bool:
        return all(cell!=0 for row in board for cell in row)

    def render_ascii(self, board: List[List[int]], win_line=None) -> str:
        n = len(board)
        try:
            win_set = set(tuple(x) for x in (win_line or []))
        except Exception:
            win_set = set()
        header = "   " + " ".join(f"{i:2d}" for i in range(n))
        lines = [header]
        for y in range(n):
            row = f"{y:2d} "
            for x in range(n):
                v = board[y][x]
                if (x,y) in win_set:
                    ch = "[●]" if v==1 else "[○]" if v==2 else " ."
                else:
                    ch = " ●" if v==1 else " ○" if v==2 else " ."
                row += ch
            lines.append(row)
        return "\n".join(lines)
