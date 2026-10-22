"""Размещение графа и математика свободной камеры, без зависимости от GUI."""

from dataclasses import dataclass
import math
import random
from typing import Callable, Optional

from .core import Maze

Vec3 = tuple[float, float, float]


def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(a: Vec3, factor: float) -> Vec3:
    return (a[0] * factor, a[1] * factor, a[2] * factor)


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def length(a: Vec3) -> float:
    return math.sqrt(dot(a, a))


def edges_of(maze: Maze) -> list[tuple[int, int]]:
    """Каждое неориентированное ребро ровно один раз."""
    return sorted((a, b) for a, room in maze.rooms.items() for b in room.neighbors if a < b)


def layout_graph(maze: Maze, cancelled: Callable[[], bool] = lambda: False) -> dict[int, Vec3]:
    """Детерминированное пружинное размещение в 3D; граф не меняется.

    Комнаты отталкиваются, связи притягивают. O(iterations * N²), O(N + E)
    памяти. Коллизии физических помещений здесь намеренно не моделируются.
    """
    numbers = sorted(maze.rooms)
    count = len(numbers)
    if count == 1:
        return {numbers[0]: (0.0, 0.0, 0.0)}
    rng = random.Random(maze.seed)
    extent = count ** (1 / 3) * 4
    points = [[rng.uniform(-extent, extent) for _ in range(3)] for _ in numbers]
    indices = {number: index for index, number in enumerate(numbers)}
    edges = [(indices[a], indices[b]) for a, b in edges_of(maze)]
    iterations = 150 if count <= 250 else 70
    spring = 7.0
    for iteration in range(iterations):
        if cancelled():
            return {}
        forces = [[0.0, 0.0, 0.0] for _ in numbers]
        for i in range(count):
            for j in range(i):
                dx = points[i][0] - points[j][0]
                dy = points[i][1] - points[j][1]
                dz = points[i][2] - points[j][2]
                distance_sq = dx * dx + dy * dy + dz * dz + 0.01
                factor = spring * spring / distance_sq
                for axis, delta in enumerate((dx, dy, dz)):
                    force = delta * factor
                    forces[i][axis] += force
                    forces[j][axis] -= force
        for i, j in edges:
            delta = [points[i][axis] - points[j][axis] for axis in range(3)]
            factor = math.sqrt(sum(value * value for value in delta)) / spring
            for axis in range(3):
                force = delta[axis] * factor
                forces[i][axis] -= force
                forces[j][axis] += force
        temperature = 2.8 * (1 - iteration / iterations) ** 1.5 + 0.02
        for i in range(count):
            force = [forces[i][axis] - 0.02 * points[i][axis] for axis in range(3)]
            magnitude = math.sqrt(sum(value * value for value in force))
            step = min(temperature, magnitude) / max(magnitude, 1e-9)
            for axis in range(3):
                points[i][axis] += force[axis] * step
    center = [(min(p[a] for p in points) + max(p[a] for p in points)) / 2 for a in range(3)]
    return {number: tuple(points[i][a] - center[a] for a in range(3)) for i, number in enumerate(numbers)}


@dataclass
class Camera:
    position: Vec3 = (0.0, -80.0, 25.0)
    yaw: float = 0.0
    pitch: float = 0.0
    fov: float = 60.0
    near: float = 0.1

    def basis(self) -> tuple[Vec3, Vec3, Vec3]:
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        sy, cy, sp, cp = math.sin(yaw), math.cos(yaw), math.sin(pitch), math.cos(pitch)
        return (cy, -sy, 0.0), (-sy * sp, -cy * sp, cp), (sy * cp, cy * cp, sp)

    def rotate(self, yaw: float, pitch: float) -> None:
        self.yaw = (self.yaw + yaw) % 360
        self.pitch = max(-89.0, min(89.0, self.pitch + pitch))

    def move(self, right: float, forward: float, up: float, distance: float) -> None:
        right_axis, _, forward_axis = self.basis()
        movement = add(add(scale(right_axis, right), scale(forward_axis, forward)), (0.0, 0.0, up))
        magnitude = length(movement)
        if magnitude > 1e-9:
            self.position = add(self.position, scale(movement, distance / magnitude))

    def view(self, point: Vec3) -> Vec3:
        delta = add(point, scale(self.position, -1))
        right, up, forward = self.basis()
        return dot(delta, right), dot(delta, up), dot(delta, forward)

    def project_view(self, point: Vec3, width: int, height: int) -> tuple[float, float]:
        focal = height / (2 * math.tan(math.radians(self.fov) / 2))
        return width / 2 + point[0] * focal / point[2], height / 2 - point[1] * focal / point[2]

    def project(self, point: Vec3, width: int, height: int) -> Optional[tuple[float, float, float]]:
        view = self.view(point)
        if view[2] < self.near:
            return None
        x, y = self.project_view(view, width, height)
        return x, y, view[2]

    def segment(self, a: Vec3, b: Vec3, width: int, height: int) -> Optional[tuple[float, ...]]:
        first, second = self.view(a), self.view(b)
        if first[2] < self.near and second[2] < self.near:
            return None
        if first[2] < self.near or second[2] < self.near:
            t = (self.near - first[2]) / (second[2] - first[2])
            clipped = tuple(first[i] + t * (second[i] - first[i]) for i in range(3))
            if first[2] < self.near:
                first = clipped
            else:
                second = clipped
        x1, y1 = self.project_view(first, width, height)
        x2, y2 = self.project_view(second, width, height)
        # Liang–Barsky: не отдаём Canvas гигантские координаты у камеры.
        dx, dy = x2 - x1, y2 - y1
        lo, hi = 0.0, 1.0
        for p, q in ((-dx, x1), (dx, width - x1), (-dy, y1), (dy, height - y1)):
            if abs(p) < 1e-12:
                if q < 0:
                    return None
            elif p < 0:
                lo = max(lo, q / p)
            else:
                hi = min(hi, q / p)
            if lo > hi:
                return None
        return x1 + lo * dx, y1 + lo * dy, x1 + hi * dx, y1 + hi * dy

    def fit(self, points: list[Vec3], width: int, height: int) -> float:
        center = tuple((min(p[a] for p in points) + max(p[a] for p in points)) / 2 for a in range(3))
        radius = max(5.0, max(length(add(p, scale(center, -1))) for p in points))
        half_vertical = math.radians(self.fov) / 2
        half_horizontal = math.atan(math.tan(half_vertical) * max(width, 1) / max(height, 1))
        distance = radius / math.sin(min(half_vertical, half_horizontal)) * 1.12
        self.yaw, self.pitch = -25.0, -18.0
        self.position = add(center, scale(self.basis()[2], -distance))
        return radius
