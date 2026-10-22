import math
import unittest

from maze import MazeConfig, generate_maze
from maze.spatial import Camera, add, dot, edges_of, layout_graph, length, scale


class LayoutTests(unittest.TestCase):
    def test_layout_preserves_graph_and_is_reproducible(self):
        maze = generate_maze(MazeConfig(35, 30, 42))
        original_rooms = dict(maze.rooms)
        first = layout_graph(maze)
        self.assertEqual(first, layout_graph(maze))
        self.assertEqual(set(first), set(maze.rooms))
        self.assertEqual(len(set(first.values())), len(maze.rooms))
        self.assertEqual(maze.rooms, original_rooms)
        self.assertTrue(all(math.isfinite(value) for point in first.values() for value in point))
        for axis in range(3):
            self.assertGreater(max(p[axis] for p in first.values()) - min(p[axis] for p in first.values()), 1)
        self.assertEqual(len(maze.shortest_path()), maze.config.path_room_count)

    def test_single_room_and_cancellation(self):
        maze = generate_maze(MazeConfig(1, 30, 5))
        self.assertEqual(layout_graph(maze), {1: (0.0, 0.0, 0.0)})
        self.assertEqual(layout_graph(generate_maze(), cancelled=lambda: True), {})

    def test_edges_are_unique_and_match_original_graph(self):
        maze = generate_maze(MazeConfig(seed=7))
        edges = edges_of(maze)
        self.assertEqual(len(edges), len(set(edges)))
        self.assertTrue(all(a < b for a, b in edges))
        self.assertEqual(len(edges) * 2, sum(len(r.neighbors) for r in maze.rooms.values()))
        for a, b in edges:
            self.assertIn(b, maze.rooms[a].neighbors)


class CameraTests(unittest.TestCase):
    def test_camera_basis_and_direction(self):
        for yaw in (0, 32, 90, 180, 270):
            for pitch in (-89, -30, 0, 60, 89):
                camera = Camera(yaw=yaw, pitch=pitch)
                axes = camera.basis()
                for axis in axes:
                    self.assertAlmostEqual(length(axis), 1)
                for i, j in ((0, 1), (1, 2), (0, 2)):
                    self.assertAlmostEqual(dot(axes[i], axes[j]), 0)
                ahead = add(camera.position, scale(axes[2], 20))
                projected = camera.project(ahead, 800, 600)
                self.assertIsNotNone(projected)
                self.assertAlmostEqual(projected[0], 400)
                self.assertAlmostEqual(projected[1], 300)
                self.assertIsNone(camera.project(camera.position, 800, 600))

    def test_normalized_motion_and_pitch_limits(self):
        camera = Camera(position=(0, 0, 0))
        camera.move(1, 1, 1, 10)
        self.assertAlmostEqual(length(camera.position), 10)
        camera.rotate(800, 1000)
        self.assertEqual(camera.yaw, 80)
        self.assertEqual(camera.pitch, 89)
        camera.rotate(-200, -1000)
        self.assertEqual(camera.yaw, 240)
        self.assertEqual(camera.pitch, -89)

    def test_projection_rejects_behind_camera_and_scales_with_depth(self):
        camera = Camera(position=(0, 0, 0))
        self.assertIsNone(camera.project((1, -10, 1), 800, 600))
        near = camera.project((1, 10, 1), 800, 600)
        far = camera.project((1, 20, 1), 800, 600)
        self.assertAlmostEqual(near[0] - 400, 2 * (far[0] - 400))
        self.assertLess(near[1], 300)

    def test_lines_clip_at_near_plane_and_viewport(self):
        camera = Camera(position=(0, 0, 0))
        self.assertIsNone(camera.segment((0, -10, 0), (2, -1, 1), 800, 600))
        self.assertIsNone(camera.segment((1000, 1, 0), (1001, 1, 0), 800, 600))
        for first, second in (((-2, -5, 0), (2, 10, 0)), ((-1000, 10, 0), (1000, 10, 0))):
            segment = camera.segment(first, second, 800, 600)
            self.assertIsNotNone(segment)
            self.assertTrue(all(math.isfinite(v) for v in segment))
            self.assertTrue(all(-1e-6 <= segment[i] <= 800 + 1e-6 for i in (0, 2)))
            self.assertTrue(all(-1e-6 <= segment[i] <= 600 + 1e-6 for i in (1, 3)))

    def test_fit_keeps_entire_graph_visible_in_different_aspect_ratios(self):
        points = list(layout_graph(generate_maze(MazeConfig(30, 30, 42))).values())
        for width, height in ((1000, 600), (300, 900), (900, 300)):
            camera = Camera()
            camera.fit(points, width, height)
            for point in points:
                x, y, depth = camera.project(point, width, height)
                self.assertTrue(0 < x < width)
                self.assertTrue(0 < y < height)
                self.assertGreater(depth, camera.near)


if __name__ == "__main__":
    unittest.main()
