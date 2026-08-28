"""BaseGame abstraction for Game Arena."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

class BaseGame(ABC):
    @abstractmethod
    def create_board(self, size: int) -> List[List[int]]:
        pass

    @abstractmethod
    def check_win(self, board: List[List[int]], x: int, y: int, color: int) -> Tuple[bool, List[Tuple[int,int]]]:
        pass

    @abstractmethod
    def is_draw(self, board: List[List[int]]) -> bool:
        pass
