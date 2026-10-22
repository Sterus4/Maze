"""Оконный просмотрщик графа: python -m maze.viewer. Только стандартная библиотека."""

import argparse
import math
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from .core import MazeConfig, generate_maze
from .spatial import Camera, add, edges_of, layout_graph, scale


BG = "#0b1220"
PANEL = "#121e30"
TEXT = "#e4edf8"
MUTED = "#8d9eb6"
CYAN = "#65d7f0"
GOLD = "#ffcc70"
GREEN = "#69e7a7"
PINK = "#ff7d9c"
MAX_ROOMS = 1000


class MazeViewer:
    def __init__(self, root: tk.Tk, config: MazeConfig):
        self.root = root
        root.title("Maze — 3D-просмотр лабиринта")
        root.geometry("1220x800")
        root.minsize(960, 740)
        root.configure(bg=BG)
        self.camera = Camera()
        self.maze = None
        self.positions = {}
        self.edges = []
        self.path_edges = set()
        self.path_rooms = set()
        self.selected = None
        self.projected = []
        self.radius = 30.0
        self.keys = set()
        self.drag = None
        self.dirty = True
        self.closed = False
        self.cancel = threading.Event()
        self.results = queue.Queue()
        self.generation = 0
        self.last_frame = time.perf_counter()
        self.show_path = tk.BooleanVar(value=True)
        self.show_labels = tk.BooleanVar(value=False)
        self.show_grid = tk.BooleanVar(value=True)
        self.rooms_value = tk.StringVar(value=str(config.room_count))
        self.percent_value = tk.StringVar(value=f"{config.path_percent:g}")
        self.seed_value = tk.StringVar(value="" if config.seed is None else str(config.seed))
        self.speed = tk.DoubleVar(value=25)
        self.message = tk.StringVar(value="Размещаем комнаты в пространстве…")
        self.stats = tk.StringVar(value="")
        self.details = tk.StringVar(value="Щёлкните по комнате,\nчтобы увидеть её связи.")
        self._build_ui()
        self._bind_controls()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.generate()
        self.timer = root.after(16, self._frame)

    def _label(self, parent, text=None, variable=None, size=10, color=TEXT, **kwargs):
        label = tk.Label(parent, text=text, textvariable=variable, bg=parent.cget("bg"),
                         fg=color, font=("Segoe UI", size), anchor="w", justify="left", **kwargs)
        label.pack(fill="x", pady=3)
        return label

    def _button(self, parent, text, command, primary=False):
        button = tk.Button(parent, text=text, command=command, relief="flat", bd=0,
                           bg=CYAN if primary else "#23334b", fg=BG if primary else TEXT,
                           activebackground="#a3e8f7", activeforeground=BG,
                           font=("Segoe UI", 10), pady=7, cursor="hand2")
        button.pack(fill="x", pady=4)
        return button

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG, padx=22, pady=14)
        header.pack(fill="x")
        self._label(header, "MAZE   /   ОБЪЁМНЫЙ ГРАФ", size=20)
        self._label(header, "Комнаты и переходы в трёх измерениях · свободная камера", color=MUTED)
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=16)
        sidebar_shell = tk.Frame(body, bg=PANEL, width=280)
        sidebar_shell.pack(side="right", fill="y", padx=(12, 0))
        sidebar_shell.pack_propagate(False)
        self.sidebar_canvas = tk.Canvas(sidebar_shell, bg=PANEL, highlightthickness=0, width=266)
        scrollbar = tk.Scrollbar(sidebar_shell, orient="vertical", command=self.sidebar_canvas.yview,
                                 width=10, bd=0, highlightthickness=0)
        scrollbar.pack(side="right", fill="y")
        self.sidebar_canvas.pack(side="left", fill="both", expand=True)
        self.sidebar_canvas.configure(yscrollcommand=scrollbar.set)
        sidebar = tk.Frame(self.sidebar_canvas, bg=PANEL, padx=14, pady=12)
        sidebar_id = self.sidebar_canvas.create_window((0, 0), window=sidebar, anchor="nw")
        sidebar.bind("<Configure>", lambda event: self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all")))
        self.sidebar_canvas.bind("<Configure>", lambda event: self.sidebar_canvas.itemconfigure(sidebar_id, width=event.width))
        self._label(sidebar, "ЛАБИРИНТ", color=CYAN, size=11)
        row = tk.Frame(sidebar, bg=PANEL)
        row.pack(fill="x", pady=4)
        for label, variable in (("Комнат", self.rooms_value), ("Путь, %", self.percent_value)):
            cell = tk.Frame(row, bg=PANEL)
            cell.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self._label(cell, label, color=MUTED, size=9)
            self._entry(cell, variable, width=9)
        self._label(sidebar, "Seed · пустое поле = случайный", color=MUTED, size=9)
        self._entry(sidebar, self.seed_value, width=24)
        self.generate_button = self._button(sidebar, "Построить лабиринт", self.generate, primary=True)
        self.random_button = self._button(sidebar, "Новый случайный лабиринт", self.randomize)
        self._label(sidebar, variable=self.stats, size=10)
        tk.Frame(sidebar, bg="#2b3a50", height=1).pack(fill="x", pady=9)
        for label, variable in (("Кратчайший путь  ·  P", self.show_path),
                                ("Номера комнат  ·  L", self.show_labels),
                                ("Опорная сетка", self.show_grid)):
            tk.Checkbutton(sidebar, text=label, variable=variable, command=self.invalidate,
                           bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL,
                           activeforeground=TEXT, font=("Segoe UI", 10), anchor="w").pack(fill="x")
        self._button(sidebar, "Общий вид  ·  Home / F", self.fit)
        self._label(sidebar, "Скорость полёта", color=MUTED, size=9)
        tk.Scale(sidebar, from_=2, to=150, variable=self.speed, orient="horizontal",
                 bg=PANEL, fg=MUTED, troughcolor=BG, highlightthickness=0,
                 activebackground=CYAN, length=220).pack(fill="x")
        self._label(sidebar, "ВЫБРАННАЯ КОМНАТА", color=CYAN, size=10)
        self._label(sidebar, variable=self.details, size=9, wraplength=232)
        self._button(sidebar, "Подлететь к комнате  ·  Enter", self.focus_selected)

        def bind_scroll(widget):
            widget.bind("<MouseWheel>", lambda event: self._scroll_sidebar(-int(event.delta / 120)))
            widget.bind("<Button-4>", lambda event: self._scroll_sidebar(-1))
            widget.bind("<Button-5>", lambda event: self._scroll_sidebar(1))
            for child in widget.winfo_children():
                bind_scroll(child)

        bind_scroll(sidebar)
        self.sidebar_canvas.bind("<MouseWheel>", lambda event: self._scroll_sidebar(-int(event.delta / 120)))

        viewport = tk.Frame(body, bg=BG)
        viewport.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(viewport, bg=BG, highlightthickness=1, highlightbackground="#26344a",
                                takefocus=True, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        legend = tk.Frame(viewport, bg=BG, pady=8)
        legend.pack(fill="x")
        for label, color in (("●  Вход", GREEN), ("●  Выход", PINK), ("●  Основной путь", GOLD),
                             ("●  Ответвления", CYAN)):
            tk.Label(legend, text=label, fg=color, bg=BG, font=("Segoe UI", 9)).pack(side="left", padx=9)
        footer = tk.Frame(self.root, bg=BG, padx=22, pady=8)
        footer.pack(fill="x")
        self._label(footer, "WASD — полёт   ·   Q / E — вниз / вверх   ·   Shift — быстрее   ·   ПКМ + мышь / стрелки — обзор   ·   Колесо — вперёд / назад", color=MUTED, size=9)
        self._label(footer, variable=self.message, color=CYAN, size=9)

    def _entry(self, parent, variable, width):
        entry = tk.Entry(parent, textvariable=variable, width=width, bg=BG, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=("Segoe UI", 11))
        entry.pack(fill="x", ipady=5)
        entry.bind("<Return>", lambda event: self.generate())

    def _scroll_sidebar(self, amount):
        if self.sidebar_canvas.yview() != (0.0, 1.0):
            self.sidebar_canvas.yview_scroll(amount, "units")
        return "break"

    def _bind_controls(self):
        canvas = self.canvas
        canvas.bind("<Configure>", lambda event: self.invalidate())
        canvas.bind("<Button-1>", self.select)
        canvas.bind("<Double-Button-1>", self._double_click)
        canvas.bind("<ButtonPress-3>", self._start_drag)
        canvas.bind("<B3-Motion>", self._look)
        canvas.bind("<ButtonRelease-3>", lambda event: setattr(self, "drag", None))
        canvas.bind("<MouseWheel>", lambda event: self._wheel(event.delta / 120))
        canvas.bind("<Button-4>", lambda event: self._wheel(1))
        canvas.bind("<Button-5>", lambda event: self._wheel(-1))
        canvas.bind("<KeyPress>", self._key_down)
        canvas.bind("<KeyRelease>", self._key_up)
        canvas.bind("<FocusOut>", self._clear_keys)

    @staticmethod
    def _key(event):
        name = event.keysym.lower()
        # Физические клавиши привычного управления и при русской раскладке.
        if event.keycode in (87, 65, 83, 68, 81, 69, 70, 80, 76) and sys.platform == "win32":
            return chr(event.keycode).lower()
        return name

    def _key_down(self, event):
        key = self._key(event)
        if key in self.keys:
            return
        self.keys.add(key)
        if key in {"home", "f"}:
            self.fit()
        elif key == "p":
            self.show_path.set(not self.show_path.get())
        elif key == "l":
            self.show_labels.set(not self.show_labels.get())
        elif key == "return":
            self.focus_selected()
        elif key == "escape":
            self._clear_keys()
        self.invalidate()

    def _key_up(self, event):
        self.keys.discard(self._key(event))

    def _clear_keys(self, event=None):
        self.keys.clear()
        self.drag = None

    def _start_drag(self, event):
        self.canvas.focus_set()
        self.drag = (event.x, event.y)

    def _look(self, event):
        if self.drag is not None:
            self.camera.rotate((event.x - self.drag[0]) * 0.25, (self.drag[1] - event.y) * 0.25)
            self.drag = (event.x, event.y)
            self.invalidate()

    def _wheel(self, steps):
        self.canvas.focus_set()
        self.camera.move(0, 1 if steps > 0 else -1, 0, abs(steps) * self.speed.get() * 0.18)
        self.invalidate()

    def _double_click(self, event):
        self.select(event)
        self.focus_selected()

    def select(self, event):
        self.canvas.focus_set()
        candidates = [(depth, number) for number, x, y, depth, radius in self.projected
                      if (x - event.x) ** 2 + (y - event.y) ** 2 <= max(10, radius + 3) ** 2]
        self.selected = min(candidates)[1] if candidates else None
        if self.selected is not None:
            room = self.maze.rooms[self.selected]
            role = "Вход и выход" if room.is_entrance and room.is_exit else "Вход" if room.is_entrance else "Выход" if room.is_exit else "Комната"
            neighbors = ", ".join(map(str, sorted(room.neighbors))) or "нет"
            self.details.set(f"{role} №{room.number} · дверей: {room.door_count}\nСвязи: {neighbors}")
        else:
            self.details.set("Щёлкните по комнате,\nчтобы увидеть её связи.")
        self.invalidate()

    def focus_selected(self):
        if self.selected in self.positions:
            self.camera.position = add(self.positions[self.selected], scale(self.camera.basis()[2], -12))
            self.canvas.focus_set()
            self.invalidate()

    def fit(self):
        if self.positions:
            self.radius = self.camera.fit(list(self.positions.values()), max(1, self.canvas.winfo_width()),
                                          max(1, self.canvas.winfo_height()))
            self.canvas.focus_set()
            self.invalidate()

    def invalidate(self):
        self.dirty = True

    def randomize(self):
        self.seed_value.set("")
        self.generate()

    def generate(self):
        try:
            seed_text = self.seed_value.get().strip()
            config = MazeConfig(int(self.rooms_value.get()), float(self.percent_value.get().replace(",", ".")),
                                int(seed_text) if seed_text else None)
            if config.room_count > MAX_ROOMS:
                raise ValueError(f"В 3D-просмотрщике поддерживается до {MAX_ROOMS} комнат.")
        except ValueError as error:
            messagebox.showerror("Проверьте параметры", str(error), parent=self.root)
            return
        self.cancel.set()
        self.cancel = threading.Event()
        self.generation += 1
        generation, cancel = self.generation, self.cancel
        self.message.set("Размещаем комнаты в 3D… Окно остаётся доступным.")

        def work():
            try:
                maze = generate_maze(config)
                positions = layout_graph(maze, cancel.is_set)
                if not cancel.is_set():
                    self.results.put((generation, maze, positions, None))
            except Exception as error:
                self.results.put((generation, None, None, str(error)))

        threading.Thread(target=work, daemon=True).start()

    def _receive_results(self):
        while True:
            try:
                generation, maze, positions, error = self.results.get_nowait()
            except queue.Empty:
                return
            if generation != self.generation:
                continue
            if error is not None:
                self.message.set(f"Не удалось построить лабиринт: {error}")
                continue
            self.maze, self.positions = maze, positions
            self.edges = edges_of(maze)
            self.path_rooms = set(maze.main_path)
            self.path_edges = {tuple(sorted(pair)) for pair in zip(maze.main_path, maze.main_path[1:])}
            self.selected = None
            self.details.set("Щёлкните по комнате,\nчтобы увидеть её связи.")
            self.seed_value.set(str(maze.seed))
            self.stats.set(f"{len(maze.rooms)} комнат · {len(self.edges)} связей\nПуть: {len(maze.main_path)} комнат\nНезависимых циклов: {maze.cycle_count}")
            self.message.set("Готово. Щёлкните по сцене для управления. Двойной щелчок по комнате — подлететь.")
            self._clear_keys()
            self.fit()

    def _frame(self):
        if self.closed:
            return
        self._receive_results()
        now = time.perf_counter()
        dt = min(0.05, now - self.last_frame)
        self.last_frame = now
        right = int("d" in self.keys) - int("a" in self.keys)
        forward = int("w" in self.keys) - int("s" in self.keys)
        up = int("e" in self.keys) - int("q" in self.keys)
        yaw = int("right" in self.keys) - int("left" in self.keys)
        pitch = int("up" in self.keys) - int("down" in self.keys)
        if right or forward or up or yaw or pitch:
            multiplier = 3 if {"shift_l", "shift_r"} & self.keys else 1
            self.camera.rotate(yaw * dt * 65, pitch * dt * 65)
            self.camera.move(right, forward, up, self.speed.get() * multiplier * dt)
            self.dirty = True
        if self.dirty:
            self.draw()
            self.dirty = False
        self.timer = self.root.after(16, self._frame)

    def _line(self, first, second, width, height, color, thickness=1):
        projected = self.camera.segment(first, second, width, height)
        if projected:
            self.canvas.create_line(*projected, fill=color, width=thickness)

    def draw(self):
        canvas = self.canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        self.projected = []
        if not self.positions:
            canvas.create_text(width / 2, height / 2, text="Размещаем комнаты…", fill=MUTED, font=("Segoe UI", 15))
            return
        if self.show_grid.get():
            floor = min(point[2] for point in self.positions.values()) - 5
            extent = math.ceil(self.radius / 10) * 10
            step = max(5, round(extent / 10))
            for i in range(-extent, extent + 1, step):
                self._line((i, -extent, floor), (i, extent, floor), width, height, "#172438")
                self._line((-extent, i, floor), (extent, i, floor), width, height, "#172438")
        path_on = self.show_path.get()
        # Дальние связи рисуются первыми. Это схема графа, не физические стены.
        ordered = sorted(self.edges, key=lambda e: self.camera.view(self.positions[e[0]])[2] + self.camera.view(self.positions[e[1]])[2], reverse=True)
        for first, second in ordered:
            selected = self.selected in (first, second)
            on_path = path_on and (first, second) in self.path_edges
            color = "#edf7ff" if selected else GOLD if on_path else "#426883"
            self._line(self.positions[first], self.positions[second], width, height, color, 2.4 if selected or on_path else 1.2)
        for number, point in self.positions.items():
            projected = self.camera.project(point, width, height)
            if projected:
                x, y, depth = projected
                radius = max(3.0, min(16.0, height * 0.55 / depth))
                if -20 <= x <= width + 20 and -20 <= y <= height + 20:
                    self.projected.append((number, x, y, depth, radius))
        for number, x, y, depth, radius in sorted(self.projected, key=lambda p: p[3], reverse=True):
            color = GOLD if path_on and number in self.path_rooms else CYAN
            if number == self.maze.entrance:
                color = GREEN
            if number == self.maze.exit:
                color = PINK if number != self.maze.entrance else GREEN
            if number == self.selected:
                canvas.create_oval(x-radius-5, y-radius-5, x+radius+5, y+radius+5, outline=TEXT, width=2)
            canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill=color, outline=BG, width=1.5)
            endpoint = number in (self.maze.entrance, self.maze.exit)
            if endpoint or self.show_labels.get() or number == self.selected:
                prefix = "ВХОД / ВЫХОД" if self.maze.entrance == self.maze.exit else "ВХОД" if number == self.maze.entrance else "ВЫХОД" if number == self.maze.exit else ""
                canvas.create_text(x+radius+5, y-5, text=f"{prefix} {number}".strip(), anchor="sw", fill=color, font=("Segoe UI", 9))
        self._axes(width, height)
        canvas.create_text(18, 16, anchor="nw", text="СВОБОДНАЯ КАМЕРА", fill=MUTED, font=("Segoe UI", 9))
        canvas.create_text(width-16, height-16, anchor="se", text=f"В кадре: {len(self.projected)} / {len(self.positions)}", fill=MUTED, font=("Segoe UI", 9))

    def _axes(self, width, height):
        x, y = 48, height - 48
        right, up, _ = self.camera.basis()
        for index, (name, color) in enumerate((("X", PINK), ("Y", GREEN), ("Z", CYAN))):
            end_x, end_y = x + right[index] * 25, y - up[index] * 25
            self.canvas.create_line(x, y, end_x, end_y, fill=color, width=2)
            self.canvas.create_text(end_x + 7, end_y - 7, text=name, fill=color, font=("Segoe UI", 8))

    def close(self):
        self.closed = True
        self.cancel.set()
        self.root.after_cancel(self.timer)
        self.root.destroy()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="3D-просмотр графа лабиринта со свободной камерой.")
    parser.add_argument("--rooms", type=int, default=100, help=f"число комнат: 1–{MAX_ROOMS}")
    parser.add_argument("--path-percent", type=float, default=30, help="процент комнат кратчайшего пути")
    parser.add_argument("--seed", type=int, help="seed для повторения графа и его размещения")
    args = parser.parse_args(argv)
    try:
        config = MazeConfig(args.rooms, args.path_percent, args.seed)
        if config.room_count > MAX_ROOMS:
            raise ValueError(f"В просмотрщике поддерживается до {MAX_ROOMS} комнат.")
    except ValueError as error:
        parser.error(str(error))
    try:
        root = tk.Tk()
    except tk.TclError as error:
        parser.exit(1, f"Не удалось открыть окно Tk: {error}\n")
    MazeViewer(root, config)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
