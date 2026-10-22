"""Export existing Python mazes and stable door positions for the Android prototype."""

import argparse
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maze import MazeConfig, generate_maze


def export_maze(config: MazeConfig, title: str, identity: str) -> dict:
    maze = generate_maze(config)
    rng = random.Random(maze.seed ^ 0x4D415A45)
    rooms = []
    for number in sorted(maze.rooms):
        room = maze.rooms[number]
        slots = list(range(4))
        rng.shuffle(slots)
        doors = [{"kind": "room", "target": target} for target in sorted(room.neighbors)]
        if room.is_entrance:
            doors.append({"kind": "entrance", "target": -1})
        if room.is_exit:
            doors.append({"kind": "exit", "target": -1})
        for door, slot in zip(doors, slots):
            door["wall"] = slot
        rooms.append({"id": number, "doors": doors})
    return {"id": identity, "title": title, "seed": str(maze.seed), "room_count": len(rooms),
            "path_percent": config.path_percent, "entrance": maze.entrance, "exit": maze.exit,
            "path_rooms": len(maze.main_path), "rooms": rooms}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rooms", type=int, help="export one custom maze instead of the bundled set")
    parser.add_argument("--path-percent", type=float, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=ROOT / "android-game" / "data" / "mazes.json")
    args = parser.parse_args()
    if args.rooms is not None:
        try:
            config = MazeConfig(args.rooms, args.path_percent, args.seed)
        except ValueError as error:
            parser.error(str(error))
        mazes = [export_maze(config, f"Лабиринт · {args.rooms} комнат", "custom")]
    else:
        mazes = [export_maze(MazeConfig(12, 50, 19), "Знакомство · 12 комнат", "intro"),
                 export_maze(MazeConfig(40, 40, 7), "Исследование · 40 комнат", "explore"),
                 export_maze(MazeConfig(100, 30, 42), "Большой лабиринт · 100 комнат", "classic")]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": 1, "mazes": mazes}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(mazes)} mazes to {args.output}")


if __name__ == "__main__":
    main()
