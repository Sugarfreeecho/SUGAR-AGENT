"""SVG render for gomoku & go - improved."""
from __future__ import annotations
from typing import List, Tuple, Optional, Dict


def render_ascii(
    board: List[List[int]],
    win_line: Optional[List[Tuple[int, int]]] = None,
) -> str:
    if not board or not board[0]:
        return "(empty board)"
    width = len(board[0])
    win_set = {tuple(item) for item in (win_line or [])}
    lines = ["   " + " ".join(f"{index:2d}" for index in range(width))]
    for y, row in enumerate(board):
        cells = []
        for x, value in enumerate(row):
            stone = "●" if value == 1 else "○" if value == 2 else "."
            if (x, y) in win_set and value:
                stone = f"[{stone}]"
            else:
                stone = f" {stone}"
            cells.append(stone)
        lines.append(f"{y:2d} " + " ".join(cells))
    return "\n".join(lines)


def render_ascii_go(
    board: List[List[int]],
    last_move: Optional[Tuple[int, int]] = None,
    ko: Optional[Tuple[int, int]] = None,
    captures: Optional[Dict] = None,
    territory_board: Optional[List[List[int]]] = None,
) -> str:
    if not board or not board[0]:
        return "(empty board)"
    n = len(board[0])
    lines = ["   " + " ".join(f"{i:2d}" for i in range(n))]
    for y, row in enumerate(board):
        cells = []
        for x, v in enumerate(row):
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
            cells.append(ch)
        lines.append(f"{y:2d} " + " ".join(cells))
    if captures:
        lines.append(f"captures B:{captures.get('black',0)} W:{captures.get('white',0)}  ko:{ko or '-'}")
    return "\n".join(lines)


def render_svg(board: List[List[int]], win_line: Optional[List[Tuple[int,int]]]=None, last_move: Optional[Tuple[int,int]]=None) -> str:
    if not board or not board[0]:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect width="100%" height="100%" fill="#e8c07a"/><text x="200" y="200" text-anchor="middle" fill="#6b4a2b">Empty board</text></svg>'
    n = len(board)
    # responsive cell size
    cell = 32 if n <= 15 else 28 if n <= 19 else 32
    pad = 28
    size = n*cell + pad*2
    win_set = set(tuple(x) for x in (win_line or []))
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="max-width:100%;height:auto">']
    svg.append(f'<rect width="100%" height="100%" fill="#e8c07a" rx="12"/>')
    svg.append(f'<rect x="{pad}" y="{pad}" width="{n*cell}" height="{n*cell}" fill="#f0d9a0" rx="4"/>')
    # grid lines
    for i in range(n):
        x = pad + i*cell + cell//2
        y = pad + i*cell + cell//2
        svg.append(f'<line x1="{pad+cell//2}" y1="{y}" x2="{pad+(n-1)*cell+cell//2}" y2="{y}" stroke="#6b4a2b" stroke-width="1" opacity="0.85"/>')
        svg.append(f'<line x1="{x}" y1="{pad+cell//2}" x2="{x}" y2="{pad+(n-1)*cell+cell//2}" stroke="#6b4a2b" stroke-width="1" opacity="0.85"/>')
    # star points
    if n >= 9:
        if n == 9:
            pts = [2, 4, 6]
        elif n == 13:
            pts = [3, 6, 9]
        elif n == 15:
            pts = [3, 7, 11]
        else: # 19
            pts = [3, 9, 15]
        for px in pts:
            for py in pts:
                cx = pad + px*cell + cell//2
                cy = pad + py*cell + cell//2
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="#3b2a16"/>')
    # stones
    for y in range(n):
        for x in range(n):
            v = board[y][x]
            if v == 0:
                continue
            cx = pad + x*cell + cell//2
            cy = pad + y*cell + cell//2
            is_win = (x, y) in win_set
            is_last = last_move and tuple(last_move) == (x, y)
            r = 13 if n <= 15 else 11
            if v == 1:
                fill = "#0f0f0f"
                stroke = "#000"
            else:
                fill = "#ffffff"
                stroke = "#444"
            # shadow
            svg.append(f'<circle cx="{cx+1}" cy="{cy+1}" r="{r}" fill="rgba(0,0,0,0.18)"/>')
            svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')
            if v == 2:
                svg.append(f'<circle cx="{cx-3}" cy="{cy-3}" r="3" fill="white" opacity="0.65"/>')
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#bbb" stroke-width="0.7" opacity="0.5"/>')
            if is_win:
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r+4}" fill="none" stroke="#e11d48" stroke-width="2.8"/>')
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r+4}" fill="none" stroke="#fff" stroke-width="0.8" opacity="0.9"/>')
            if is_last:
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="#e11d48" stroke="#fff" stroke-width="1.2"/>')
    # coords
    for i in range(n):
        x = pad + i*cell + cell//2
        svg.append(f'<text x="{x}" y="{pad-8}" text-anchor="middle" font-size="11" font-weight="600" fill="#5a3a1a">{i}</text>')
        y = pad + i*cell + cell//2 + 4
        svg.append(f'<text x="{pad-12}" y="{y}" text-anchor="middle" font-size="11" font-weight="600" fill="#5a3a1a">{i}</text>')
    svg.append('</svg>')
    return "\n".join(svg)


def render_svg_go(
    board: List[List[int]],
    last_move: Optional[Tuple[int, int]] = None,
    ko: Optional[Tuple[int, int]] = None,
    territory_board: Optional[List[List[int]]] = None,
    captures: Optional[Dict] = None,
) -> str:
    """Go-specific SVG: wood board, ko highlight (red X), territory tint, capture counts."""
    if not board or not board[0]:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect width="100%" height="100%" fill="#e8c07a"/><text x="200" y="200" text-anchor="middle" fill="#6b4a2b">Empty board</text></svg>'
    n = len(board)
    cell = 28 if n <= 13 else 26 if n <= 15 else 24
    pad = 28
    size = n * cell + pad * 2
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="max-width:100%;height:auto">']
    # background wood
    svg.append(f'<rect width="100%" height="100%" fill="#dcb67a" rx="12"/>')
    svg.append(f'<rect x="{pad}" y="{pad}" width="{n*cell}" height="{n*cell}" fill="#e8c07a" rx="4" stroke="#8b5a2b" stroke-width="1.2"/>')
    # grid lines
    for i in range(n):
        x = pad + i * cell + cell // 2
        y = pad + i * cell + cell // 2
        svg.append(f'<line x1="{pad+cell//2}" y1="{y}" x2="{pad+(n-1)*cell+cell//2}" y2="{y}" stroke="#5a3a1a" stroke-width="1" opacity="0.9"/>')
        svg.append(f'<line x1="{x}" y1="{pad+cell//2}" x2="{x}" y2="{pad+(n-1)*cell+cell//2}" stroke="#5a3a1a" stroke-width="1" opacity="0.9"/>')
    # star points (hoshi)
    if n >= 9:
        if n == 9:
            pts = [2, 4, 6]
        elif n == 13:
            pts = [3, 6, 9]
        elif n == 15:
            pts = [3, 7, 11]
        else:  # 19
            pts = [3, 9, 15]
        for px in pts:
            for py in pts:
                cx = pad + px * cell + cell // 2
                cy = pad + py * cell + cell // 2
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="#3b2a16"/>')

    # territory tint (subtle)
    if territory_board:
        for y in range(n):
            for x in range(n):
                if board[y][x] != 0:
                    continue
                t = territory_board[y][x]
                if t == 0:
                    continue
                cx = pad + x * cell + cell // 2
                cy = pad + y * cell + cell // 2
                color = "rgba(0,0,0,0.18)" if t == 1 else "rgba(255,255,255,0.55)"
                stroke = "#111" if t == 1 else "#fff"
                svg.append(f'<rect x="{cx-10}" y="{cy-10}" width="20" height="20" rx="3" fill="{color}" stroke="{stroke}" stroke-width="0.6" opacity="0.85"/>')
                # small square indicator
                svg.append(f'<rect x="{cx-3}" y="{cy-3}" width="6" height="6" rx="1" fill="{stroke}" opacity="0.9"/>')

    # ko highlight
    if ko:
        try:
            kx, ky = int(ko[0]), int(ko[1])
            if 0 <= kx < n and 0 <= ky < n and board[ky][kx] == 0:
                cx = pad + kx * cell + cell // 2
                cy = pad + ky * cell + cell // 2
                svg.append(f'<rect x="{cx-13}" y="{cy-13}" width="26" height="26" rx="4" fill="none" stroke="#e11d48" stroke-width="2.2" stroke-dasharray="4 3" opacity="0.95"/>')
                svg.append(f'<text x="{cx}" y="{cy+4}" text-anchor="middle" font-size="13" font-weight="900" fill="#e11d48">×</text>')
        except Exception:
            pass

    # stones
    for y in range(n):
        for x in range(n):
            v = board[y][x]
            if v == 0:
                continue
            cx = pad + x * cell + cell // 2
            cy = pad + y * cell + cell // 2
            is_last = last_move and tuple(last_move) == (x, y)
            r = 11 if n <= 13 else 10
            if v == 1:
                fill = "#0f0f0f"
                stroke = "#000"
            else:
                fill = "#ffffff"
                stroke = "#444"
            svg.append(f'<circle cx="{cx+1}" cy="{cy+1}" r="{r}" fill="rgba(0,0,0,0.18)"/>')
            svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')
            if v == 2:
                svg.append(f'<circle cx="{cx-3}" cy="{cy-3}" r="3" fill="white" opacity="0.65"/>')
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#bbb" stroke-width="0.7" opacity="0.5"/>')
            if is_last:
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="4.2" fill="#e11d48" stroke="#fff" stroke-width="1.2"/>')

    # coords
    for i in range(n):
        x = pad + i * cell + cell // 2
        svg.append(f'<text x="{x}" y="{pad-9}" text-anchor="middle" font-size="10" font-weight="700" fill="#5a3a1a">{i}</text>')
        y = pad + i * cell + cell // 2 + 4
        svg.append(f'<text x="{pad-13}" y="{y}" text-anchor="middle" font-size="10" font-weight="700" fill="#5a3a1a">{i}</text>')

    # captures legend if provided
    if captures:
        cap_text = f"提子 B:{captures.get('black',0)} W:{captures.get('white',0)}"
        svg.append(f'<text x="{size-8}" y="{size-6}" text-anchor="end" font-size="9" fill="#5a3a1a" opacity="0.75">{cap_text}</text>')

    svg.append('</svg>')
    return "\n".join(svg)
