"""Неориентированный граф комнат и независимая от терминала логика игры."""

from collections import defaultdict, deque
from dataclasses import dataclass, field
import math
import random
from typing import Optional


@dataclass(frozen=True)
class MazeConfig:
    room_count: int = 100
    path_percent: float = 30.0
    seed: Optional[int] = None

    def __post_init__(self) -> None:
        if isinstance(self.room_count, bool) or not isinstance(self.room_count, int):
            raise ValueError("Количество комнат должно быть целым числом.")
        if self.room_count < 1:
            raise ValueError("Количество комнат должно быть не меньше 1.")
        if not math.isfinite(self.path_percent) or not 0 < self.path_percent <= 100:
            raise ValueError("Процент кратчайшего пути должен быть больше 0 и не больше 100.")

    @property
    def path_room_count(self) -> int:
        # Округление половин вверх, а не банковское округление round().
        minimum = 1 if self.room_count == 1 else 2
        return max(minimum, math.floor(self.room_count * (self.path_percent / 100) + 0.5))


@dataclass(frozen=True)
class Room:
    number: int
    neighbors: tuple[int, ...]
    is_entrance: bool = False
    is_exit: bool = False

    @property
    def door_count(self) -> int:
        return len(self.neighbors) + int(self.is_entrance) + int(self.is_exit)


@dataclass(frozen=True)
class Maze:
    config: MazeConfig
    seed: int
    rooms: dict[int, Room]
    main_path: tuple[int, ...]

    @property
    def entrance(self) -> int:
        return self.main_path[0]

    @property
    def exit(self) -> int:
        return self.main_path[-1]

    @property
    def cycle_count(self) -> int:
        """Число независимых циклов связного графа: E - V + 1."""
        edges = sum(len(room.neighbors) for room in self.rooms.values()) // 2
        return edges - len(self.rooms) + 1

    def shortest_path(self, start: Optional[int] = None) -> tuple[int, ...]:
        """BFS от выбранной комнаты до выхода, включая обе конечные комнаты."""
        start = self.entrance if start is None else start
        if start not in self.rooms:
            raise ValueError("Такой комнаты нет в лабиринте.")
        parents: dict[int, Optional[int]] = {start: None}
        pending = deque([start])
        while pending:
            current = pending.popleft()
            if current == self.exit:
                result = []
                cursor: Optional[int] = current
                while cursor is not None:
                    result.append(cursor)
                    cursor = parents[cursor]
                return tuple(reversed(result))
            for neighbor in self.rooms[current].neighbors:
                if neighbor not in parents:
                    parents[neighbor] = current
                    pending.append(neighbor)
        raise ValueError("Выход недостижим.")


def generate_maze(config: Optional[MazeConfig] = None) -> Maze:
    """Создать связный лабиринт с точной длиной кратчайшего пути.

    Каждое дерево ответвлений имеет единственный корень на основном пути.
    Дополнительные рёбра соединяют только вершины одного такого дерева
    (включая корень), поэтому не создают сокращений между корнями.
    """
    config = config if config is not None else MazeConfig()
    seed = config.seed if config.seed is not None else random.SystemRandom().getrandbits(64)
    rng = random.Random(seed)
    numbers = list(range(1, config.room_count + 1))
    rng.shuffle(numbers)
    main_path = tuple(numbers[: config.path_room_count])
    entrance, exit_room = main_path[0], main_path[-1]
    adjacency: dict[int, set[int]] = {number: set() for number in numbers}
    capacity = {
        number: 4 - int(number == entrance) - int(number == exit_room)
        for number in numbers
    }

    def connect(first: int, second: int) -> None:
        adjacency[first].add(second)
        adjacency[second].add(first)

    for first, second in zip(main_path, main_path[1:]):
        connect(first, second)

    roots = {number: number for number in main_path}
    available = list(main_path)
    for number in numbers[len(main_path):]:
        index = rng.randrange(len(available))
        parent = available[index]
        connect(parent, number)
        roots[number] = roots[parent]
        if len(adjacency[parent]) == capacity[parent]:
            available[index] = available[-1]
            available.pop()
        available.append(number)

    # Ограниченное число случайных попыток на группу: без O(N²) списка пар.
    groups: dict[int, list[int]] = defaultdict(list)
    for number in numbers:
        groups[roots[number]].append(number)
    for group in groups.values():
        if len(group) < 3:
            continue
        for _ in range(2 * len(group)):
            if rng.random() >= 0.35:
                continue
            first, second = rng.sample(group, 2)
            if (
                second not in adjacency[first]
                and len(adjacency[first]) < capacity[first]
                and len(adjacency[second]) < capacity[second]
            ):
                connect(first, second)

    rooms = {}
    for number in numbers:
        neighbors = sorted(adjacency[number])
        rng.shuffle(neighbors)
        rooms[number] = Room(number, tuple(neighbors), number == entrance, number == exit_room)
    return Maze(config, seed, rooms, main_path)


@dataclass
class Game:
    maze: Maze
    current: int = field(init=False)
    visited: set[int] = field(init=False)
    history: list[int] = field(default_factory=list, init=False)
    moves: int = field(default=0, init=False)
    finished: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.current = self.maze.entrance
        self.visited = {self.current}

    def move(self, destination: int) -> None:
        if self.finished:
            raise ValueError("Игра уже завершена.")
        if destination not in self.maze.rooms[self.current].neighbors:
            raise ValueError("В эту комнату нет двери.")
        self.history.append(self.current)
        self.current = destination
        self.visited.add(destination)
        self.moves += 1

    def back(self) -> bool:
        if self.finished:
            raise ValueError("Игра уже завершена.")
        if not self.history:
            return False
        self.current = self.history.pop()
        self.moves += 1
        return True

    def leave(self) -> None:
        if self.finished:
            raise ValueError("Игра уже завершена.")
        if self.current != self.maze.exit:
            raise ValueError("Выход находится в другой комнате.")
        self.finished = True
