"""Генерация лабиринтов и состояние игры без зависимости от интерфейса."""

from .core import Game, Maze, MazeConfig, Room, generate_maze

__all__ = ["Game", "Maze", "MazeConfig", "Room", "generate_maze"]
