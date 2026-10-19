import contextlib
import io
import unittest
from unittest.mock import patch

from maze import Game, MazeConfig, generate_maze
from maze.cli import main, play


class GenerationTests(unittest.TestCase):
    def check_invariants(self, maze):
        self.assertEqual(len(maze.rooms), maze.config.room_count)
        self.assertEqual(set(maze.rooms), set(range(1, maze.config.room_count + 1)))
        self.assertEqual(len(maze.shortest_path()), maze.config.path_room_count)
        self.assertEqual(maze.shortest_path(), maze.main_path)
        self.assertEqual(sum(room.is_entrance for room in maze.rooms.values()), 1)
        self.assertEqual(sum(room.is_exit for room in maze.rooms.values()), 1)
        reached = {maze.entrance}
        pending = [maze.entrance]
        while pending:
            number = pending.pop()
            room = maze.rooms[number]
            self.assertTrue(1 <= room.door_count <= 4)
            self.assertNotIn(number, room.neighbors)
            self.assertEqual(len(room.neighbors), len(set(room.neighbors)))
            for neighbor in room.neighbors:
                self.assertIn(number, maze.rooms[neighbor].neighbors)
                if neighbor not in reached:
                    reached.add(neighbor)
                    pending.append(neighbor)
        self.assertEqual(reached, set(maze.rooms))
        for number in maze.main_path:
            self.assertGreaterEqual(maze.rooms[number].door_count, 2)

    def test_many_sizes_percentages_and_seeds(self):
        for size in (1, 2, 3, 4, 10, 100, 257):
            for percent in (0.01, 1, 30, 50, 99, 100):
                for seed in range(20):
                    with self.subTest(size=size, percent=percent, seed=seed):
                        self.check_invariants(generate_maze(MazeConfig(size, percent, seed)))

    def test_defaults_and_rounding(self):
        self.assertEqual(MazeConfig().path_room_count, 30)
        self.assertEqual(MazeConfig(15, 30).path_room_count, 5)
        self.assertEqual(MazeConfig(100, 0.1).path_room_count, 2)
        self.assertEqual(MazeConfig(1, 30).path_room_count, 1)

    def test_invalid_settings(self):
        for size in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                MazeConfig(size)
        for percent in (0, -1, 101, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                MazeConfig(path_percent=percent)

    def test_seed_reproduces_entire_maze(self):
        original = generate_maze()
        replay = generate_maze(MazeConfig(seed=original.seed))
        self.assertEqual(original.seed, replay.seed)
        self.assertEqual(original.rooms, replay.rooms)
        self.assertEqual(original.main_path, replay.main_path)
        self.assertNotEqual(generate_maze(MazeConfig(seed=1)).rooms, generate_maze(MazeConfig(seed=2)).rooms)

    def test_branches_include_cycles_and_dead_ends(self):
        mazes = [generate_maze(MazeConfig(seed=seed)) for seed in range(30)]
        self.assertTrue(any(maze.cycle_count > 0 for maze in mazes))
        self.assertTrue(any(room.door_count == 1 for maze in mazes for room in maze.rooms.values()))
        for maze in mazes:
            # После удаления основного пути у каждой компоненты ровно один корень.
            backbone = set(maze.main_path)
            remaining = set(maze.rooms) - backbone
            while remaining:
                pending = [remaining.pop()]
                anchors = set()
                while pending:
                    for neighbor in maze.rooms[pending.pop()].neighbors:
                        if neighbor in backbone:
                            anchors.add(neighbor)
                        elif neighbor in remaining:
                            remaining.remove(neighbor)
                            pending.append(neighbor)
                self.assertEqual(len(anchors), 1)

    def test_all_rooms_on_path(self):
        maze = generate_maze(MazeConfig(100, 100, 42))
        self.assertEqual(maze.cycle_count, 0)
        self.assertTrue(all(room.door_count == 2 for room in maze.rooms.values()))


class GameTests(unittest.TestCase):
    def test_walk_to_exit_and_finish(self):
        maze = generate_maze(MazeConfig(seed=42))
        game = Game(maze)
        with self.assertRaises(ValueError):
            game.leave()
        with self.assertRaises(ValueError):
            game.move(game.current)
        for number in maze.main_path[1:]:
            game.move(number)
        self.assertFalse(game.finished)
        game.leave()
        self.assertTrue(game.finished)
        self.assertEqual(game.moves, 29)
        self.assertEqual(len(game.visited), 30)
        with self.assertRaises(ValueError):
            game.move(maze.main_path[-2])
        with self.assertRaises(ValueError):
            game.back()

    def test_back_tracks_history_and_counts_actual_moves(self):
        maze = generate_maze(MazeConfig(seed=7))
        game = Game(maze)
        self.assertFalse(game.back())
        game.move(maze.main_path[1])
        game.move(maze.main_path[2])
        self.assertTrue(game.back())
        self.assertEqual(game.current, maze.main_path[1])
        self.assertTrue(game.back())
        self.assertEqual(game.current, maze.entrance)
        self.assertEqual(game.moves, 4)
        self.assertEqual(len(game.visited), 3)
        self.assertFalse(game.back())

    def test_single_room_has_separate_entry_and_exit(self):
        game = Game(generate_maze(MazeConfig(1, 30, 5)))
        self.assertEqual(game.maze.rooms[game.current].door_count, 2)
        game.leave()
        self.assertTrue(game.finished)
        self.assertEqual(game.moves, 0)


class TerminalTests(unittest.TestCase):
    def test_interactive_game_reaches_victory(self):
        maze = generate_maze(MazeConfig(25, 40, 19))
        commands = ["?", "status-invalid", "0", "999", "b", "s", "h", "l"]
        for current, following in zip(maze.main_path, maze.main_path[1:]):
            commands.append(str(maze.rooms[current].neighbors.index(following) + 1))
        commands.append(str(maze.rooms[maze.exit].door_count))
        output = io.StringIO()
        with patch("builtins.input", side_effect=commands), contextlib.redirect_stdout(output):
            play(maze)
        self.assertIn("Победа!", output.getvalue())
        self.assertIn("Переходов: 9", output.getvalue())
        self.assertIn("Подсказка:", output.getvalue())

    def test_inspection_and_solution_do_not_start_input(self):
        with patch("builtins.input", side_effect=AssertionError("Unexpected prompt")):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--seed", "42", "--solution"]), 0)
        self.assertIn("30 комнат (29 переходов", output.getvalue())
        self.assertIn("Путь:", output.getvalue())

    def test_single_room_play(self):
        with patch("builtins.input", side_effect=["1", "h", "2"]):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                main(["--rooms", "1", "--seed", "5"])
        self.assertIn("Победа!", output.getvalue())

    def test_invalid_cli_settings(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                main(["--rooms", "0"])
        self.assertEqual(result.exception.code, 2)

    def test_end_of_input_and_quit(self):
        for commands in (EOFError, KeyboardInterrupt, ["q"]):
            with patch("builtins.input", side_effect=commands):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(main(["--seed", "42"]), 0)
            self.assertIn("Игра завершена", output.getvalue())


if __name__ == "__main__":
    unittest.main()
