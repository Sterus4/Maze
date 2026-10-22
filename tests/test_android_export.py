import unittest

from maze import MazeConfig, generate_maze
from scripts.export_android_mazes import export_maze


class AndroidExportTests(unittest.TestCase):
    def test_preserves_every_edge_and_door_limit(self):
        for size in (1, 2, 12, 100):
            config = MazeConfig(size, 30, 42)
            original = generate_maze(config)
            exported = export_maze(config, "Test", "test")
            self.assertEqual(exported["entrance"], original.entrance)
            self.assertEqual(exported["exit"], original.exit)
            self.assertEqual(exported["path_rooms"], len(original.main_path))
            for room in exported["rooms"]:
                doors = room["doors"]
                self.assertEqual(len(doors), original.rooms[room["id"]].door_count)
                self.assertEqual(len({door["wall"] for door in doors}), len(doors))
                self.assertTrue(all(0 <= door["wall"] < 4 for door in doors))
                self.assertEqual({door["target"] for door in doors if door["kind"] == "room"},
                                 set(original.rooms[room["id"]].neighbors))

    def test_seed_preserves_door_positions(self):
        config = MazeConfig(100, 30, 987)
        self.assertEqual(export_maze(config, "Test", "test"), export_maze(config, "Test", "test"))


if __name__ == "__main__":
    unittest.main()
