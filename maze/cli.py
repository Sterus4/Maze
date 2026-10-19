"""Терминальный интерфейс; для будущего UI достаточно maze.core."""

import argparse
from typing import Optional

from .core import Game, Maze, MazeConfig, generate_maze


HELP = """Введите номер двери, чтобы пройти в соседнюю комнату.
  назад / b       — вернуться на один шаг по истории перемещений
  осмотр / l      — снова показать комнату
  статус / s      — посещённые комнаты и число переходов
  подсказка / h   — показать следующую дверь на кратчайшем пути
  помощь / ?      — показать команды
  выход / q       — закончить игру без победы
Чтобы победить, найдите дверь «ВЫХОД ИЗ ЛАБИРИНТА» и пройдите через неё.
"""


def describe(maze: Maze) -> None:
    length = len(maze.main_path)
    print(f"Комнат: {len(maze.rooms)}")
    print(f"Кратчайший путь: {length} комнат ({length - 1} переходов между комнатами)")
    print(f"Заданный процент: {maze.config.path_percent:g}%; фактический: {length / len(maze.rooms):.1%}")
    print(f"Независимых циклов: {maze.cycle_count}")
    print(f"Тупиковых комнат: {sum(room.door_count == 1 for room in maze.rooms.values())}")
    print(f"Seed для повторения лабиринта: {maze.seed}")


def show_room(game: Game) -> list[tuple[str, Optional[int]]]:
    room = game.maze.rooms[game.current]
    print(f"\n=== Комната №{room.number} ===")
    if room.is_entrance:
        print("Здесь находится вход в лабиринт.")
    if room.is_exit:
        print("Вы нашли выход! Осталось пройти через внешнюю дверь.")
    if room.door_count == 1:
        print("Это тупик. Можно вернуться назад.")
    doors: list[tuple[str, Optional[int]]] = [("room", number) for number in room.neighbors]
    if room.is_entrance:
        doors.append(("entrance", None))
    if room.is_exit:
        doors.append(("exit", None))
    for index, (kind, destination) in enumerate(doors, 1):
        if kind == "entrance":
            label = "Вход снаружи (начало игры)"
        elif kind == "exit":
            label = "ВЫХОД ИЗ ЛАБИРИНТА"
        else:
            marker = " — уже посещена" if destination in game.visited else ""
            label = f"Комната №{destination}{marker}"
        print(f"  {index}. {label}")
    return doors


def play(maze: Maze) -> None:
    game = Game(maze)
    print("\nЛАБИРИНТ")
    print(f"Комнат: {len(maze.rooms)}. Seed: {maze.seed}")
    print("Найдите выход. Введите «помощь» или «?» для списка команд.")
    doors = show_room(game)
    while not game.finished:
        command = input("\nДверь или команда > ").strip().lower()
        if command in {"выход", "q", "quit"}:
            print("Игра завершена. До встречи!")
            return
        if command in {"помощь", "?", "help"}:
            print(HELP)
        elif command in {"статус", "s"}:
            print(f"Посещено: {len(game.visited)}/{len(maze.rooms)}. Переходов: {game.moves}.")
        elif command in {"осмотр", "l"}:
            doors = show_room(game)
        elif command in {"назад", "b"}:
            if game.back():
                doors = show_room(game)
            else:
                print("История перемещений пуста: вы у входа.")
        elif command in {"подсказка", "h"}:
            path = maze.shortest_path(game.current)
            target = ("exit", None) if len(path) == 1 else ("room", path[1])
            print(f"Подсказка: выберите дверь {doors.index(target) + 1}.")
        else:
            try:
                index = int(command) - 1
            except ValueError:
                print("Введите номер двери или «помощь».")
                continue
            if not 0 <= index < len(doors):
                print(f"Выберите дверь от 1 до {len(doors)}.")
                continue
            kind, destination = doors[index]
            if kind == "entrance":
                print("Это дверь, через которую вы вошли. Ищите другой выход!")
            elif kind == "exit":
                game.leave()
            else:
                assert destination is not None
                game.move(destination)
                doors = show_room(game)
    print("\nПобеда! Вы выбрались из лабиринта.")
    print(f"Посещено комнат: {len(game.visited)}. Переходов: {game.moves}.")
    print(f"Минимально возможное число переходов: {len(maze.main_path) - 1}.")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Терминальная игра-лабиринт.")
    parser.add_argument("--rooms", type=int, default=100, help="количество комнат (по умолчанию 100)")
    parser.add_argument("--path-percent", type=float, default=30, help="процент комнат кратчайшего пути (по умолчанию 30)")
    parser.add_argument("--seed", type=int, help="число для воспроизводимой генерации")
    parser.add_argument("--inspect", action="store_true", help="показать параметры лабиринта без запуска игры")
    parser.add_argument("--solution", action="store_true", help="показать параметры и решение без запуска игры")
    args = parser.parse_args(argv)
    try:
        config = MazeConfig(args.rooms, args.path_percent, args.seed)
    except ValueError as error:
        parser.error(str(error))
    maze = generate_maze(config)
    if args.inspect or args.solution:
        describe(maze)
        if args.solution:
            print("Путь: " + " -> ".join(map(str, maze.shortest_path())) + " -> ВЫХОД")
        return 0
    try:
        play(maze)
    except (EOFError, KeyboardInterrupt):
        print("\nИгра завершена.")
    return 0
