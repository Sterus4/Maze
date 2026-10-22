extends SceneTree

const State = preload("res://scripts/maze_state.gd")
const Look = preload("res://scripts/look_controller.gd")
const Generator = preload("res://scripts/maze_generator.gd")
var failures := 0
var checks := 0

func expect(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		printerr("FAIL: " + message)

func _initialize() -> void:
	var catalog: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/mazes.json"))
	for data in catalog.mazes:
		var state := State.new()
		expect(state.load_maze(data), "valid exported graph")
		expect(state.enter(-1) == "invalid", "no door through a wall")
		var path := shortest(state)
		expect(path.size() == int(data.path_rooms), "shortest path length matches Python")
		var old_current: int = state.current
		for door in state.rooms[state.current].doors:
			if door.kind == "entrance":
				expect(state.enter(int(door.wall)) == "entrance", "entry is not victory")
				expect(state.current == old_current and not state.finished, "entry does not move")
		for destination in path.slice(1):
			var origin: int = state.current
			var wall := wall_to(state, int(destination))
			expect(state.enter(wall) == "moved", "forward traversal")
			expect(state.current == int(destination), "correct destination")
			var back := wall_to(state, origin)
			expect(back >= 0, "back door exists")
			expect(state.enter(back) == "moved" and state.current == origin, "back door returns")
			expect(state.enter(wall) == "moved", "return to route")
		var saved := state.snapshot()
		var restored := State.new()
		restored.load_maze(data)
		expect(restored.restore(saved), "restore saved progress")
		expect(restored.current == state.current and restored.moves == state.moves, "progress preserved")
		for door in state.rooms[state.current].doors:
			if door.kind == "exit":
				expect(state.enter(int(door.wall)) == "won", "exit completes game")
		expect(state.finished, "victory persists")
		expect(state.enter(0) == "finished", "cannot move after winning")
		var corrupt := saved.duplicate(true)
		corrupt.current = -900
		expect(not restored.restore(corrupt), "reject broken progress")
		var broken: Dictionary = data.duplicate(true)
		broken.rooms[0].doors[0].wall = 7
		expect(not State.new().load_maze(broken), "reject invalid wall slot")
	var single := {"id": "single", "seed": "1", "room_count": 1, "entrance": 1, "exit": 1,
		"rooms": [{"id": 1, "doors": [{"wall": 0, "kind": "entrance", "target": -1}, {"wall": 2, "kind": "exit", "target": -1}]}]}
	var one := State.new()
	expect(one.load_maze(single), "one room is supported")
	expect(one.enter(2) == "won" and one.moves == 0, "single room victory")
	var look := Look.new()
	look.recenter(PI / 2)
	expect(absf(look.orientation(0).length() - 1.0) < 0.0001, "normalized camera rotation")
	look.drag(Vector2(300, 150))
	expect(look.orientation(0).angle_to(Quaternion(Vector3.UP, PI / 2)) > 0.5, "touch rotates view")
	look.recenter()
	expect(look.orientation(0).is_equal_approx(Quaternion.IDENTITY), "recenter resets view")
	for count in [1, 2, 3, 7, 12, 40, 100, 501, 5000]:
		for seed_value in range(6):
			for percent in [1.0, 30.0, 100.0]:
				var generated := Generator.generate(count, seed_value, percent)
				var generated_state := State.new()
				expect(generated_state.load_maze(generated), "generated graph connected, reciprocal, 1–4 doors")
				expect(generated_state.rooms.size() == count, "custom room count")
				expect(shortest(generated_state).size() == int(generated.path_rooms), "cycles do not shorten route")
	var seeded := Generator.generate(40, 91)
	expect(seeded == Generator.generate(40, 91), "seed reproduces door placement")
	expect(seeded != Generator.generate(40, 92), "new seed changes maze")
	for count in [-1, 0, 5001]:
		expect(Generator.generate(count, 1).is_empty(), "reject invalid custom room count")
	for a in range(4):
		for b in range(4):
			var direction := Vector3.FORWARD.rotated(Vector3.UP, -a * PI / 2)
			var rotation_b := (b - a) * PI / 2 + PI
			var back_direction := Vector3.FORWARD.rotated(Vector3.UP, rotation_b - b * PI / 2)
			expect(direction.is_equal_approx(-back_direction), "opposite normals for all 16 wall pairs")
			expect((direction * 9 + back_direction * 4.5).is_equal_approx(direction * 4.5), "thresholds coincide")
	print("Game state: %d checks, %d failures" % [checks, failures])
	quit(0 if failures == 0 else 1)

func wall_to(state: MazeState, target: int) -> int:
	for door in state.rooms[state.current].doors:
		if door.kind == "room" and int(door.target) == target:
			return int(door.wall)
	return -1

func shortest(state: MazeState) -> Array:
	var parents := {state.current: -1}
	var pending := [state.current]
	while not pending.is_empty():
		var current: int = pending.pop_front()
		if current == int(state.data.exit):
			var path: Array = []
			while current != -1:
				path.push_front(current)
				current = parents[current]
			return path
		for door in state.rooms[current].doors:
			var target := int(door.target)
			if door.kind == "room" and not parents.has(target):
				parents[target] = current
				pending.append(target)
	return []
