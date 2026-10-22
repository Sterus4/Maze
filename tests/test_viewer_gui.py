"""Необязательный интеграционный тест окна: MAZE_GUI_TESTS=1."""

import os
import time
import unittest
from types import SimpleNamespace


@unittest.skipUnless(os.environ.get("MAZE_GUI_TESTS") == "1", "GUI test requires MAZE_GUI_TESTS=1 and a desktop")
class ViewerTests(unittest.TestCase):
    def test_render_camera_selection_and_regeneration(self):
        import tkinter as tk
        from maze import MazeConfig
        from maze.viewer import MazeViewer

        root = tk.Tk()
        app = MazeViewer(root, MazeConfig(30, 30, 42))
        try:
            deadline = time.perf_counter() + 15
            while app.maze is None and time.perf_counter() < deadline:
                root.update()
                time.sleep(0.01)
            self.assertIsNotNone(app.maze)
            root.update()
            app.fit()
            app.draw()
            self.assertEqual(len(app.projected), 30)
            self.assertGreater(len(app.canvas.find_all()), 30)
            # Панель прокручивается: нижние кнопки доступны и в небольшом окне.
            sidebar = app.generate_button.master
            for geometry in ("1220x800", "960x740"):
                root.geometry(geometry)
                root.update()
                for widget in sidebar.winfo_children():
                    self.assertTrue(widget.winfo_ismapped(), str(widget))
                    self.assertLessEqual(widget.winfo_y() + widget.winfo_height(), sidebar.winfo_height(), str(widget))
                app.sidebar_canvas.yview_moveto(1)
                root.update()
                last = sidebar.winfo_children()[-1]
                viewport = app.sidebar_canvas
                self.assertGreaterEqual(last.winfo_rooty(), viewport.winfo_rooty())
                self.assertLessEqual(last.winfo_rooty() + last.winfo_height(), viewport.winfo_rooty() + viewport.winfo_height())
                app.sidebar_canvas.yview_moveto(0)
            before = app.camera.position
            app._wheel(1)
            self.assertNotEqual(app.camera.position, before)
            app.fit()
            app.draw()
            number, x, y, _, _ = min(app.projected, key=lambda p: p[3])
            app.select(SimpleNamespace(x=x, y=y))
            self.assertEqual(app.selected, number)
            app.focus_selected()
            app.draw()
            self.assertIn(str(number), app.details.get())
            app.show_labels.set(True)
            app.show_path.set(False)
            app.draw()
            app.keys.add("w")
            app._clear_keys()
            self.assertFalse(app.keys)
            app.rooms_value.set("1")
            app.seed_value.set("9")
            app.generate()
            deadline = time.perf_counter() + 10
            while app.maze.config.room_count != 1 and time.perf_counter() < deadline:
                root.update()
                time.sleep(0.01)
            self.assertEqual(len(app.maze.rooms), 1)
            app.draw()
            self.assertEqual(len(app.projected), 1)
        finally:
            app.close()


if __name__ == "__main__":
    unittest.main()
