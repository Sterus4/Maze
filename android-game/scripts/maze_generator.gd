class_name MazeGenerator
extends RefCounted
## Same construction as Python: a path, rooted branches, cycles within each root.
## Seeded Godot RNG is independent from Python's RNG; graph invariants are identical.

const MAX_ROOMS := 5000

static func shuffled(values: Array, rng: RandomNumberGenerator) -> Array:
	for i in range(values.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var value: Variant = values[i]
		values[i] = values[j]
		values[j] = value
	return values

static func generate(count: int, seed_value: int, percent: float = 30.0) -> Dictionary:
	if count < 1 or count > MAX_ROOMS or not is_finite(percent) or percent <= 0 or percent > 100:
		return {}
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var numbers := shuffled(range(1, count + 1), rng)
	var path_count := maxi(1 if count == 1 else 2, int(floor(count * percent / 100.0 + 0.5)))
	var path := numbers.slice(0, path_count)
	var entrance: int = path[0]
	var exit_room: int = path[-1]
	var edges: Dictionary = {}
	var capacity: Dictionary = {}
	var roots: Dictionary = {}
	for number in numbers:
		edges[number] = []
		capacity[number] = 4 - int(number == entrance) - int(number == exit_room)
	for i in range(1, path.size()):
		edges[path[i - 1]].append(path[i])
		edges[path[i]].append(path[i - 1])
	for number in path:
		roots[number] = number
	var available := path.duplicate()
	for number in numbers.slice(path_count):
		var index := rng.randi_range(0, available.size() - 1)
		var parent: int = available[index]
		edges[parent].append(number)
		edges[number].append(parent)
		roots[number] = roots[parent]
		if edges[parent].size() == capacity[parent]:
			available[index] = available[-1]
			available.pop_back()
		available.append(number)
	var groups: Dictionary = {}
	for number in numbers:
		if not groups.has(roots[number]):
			groups[roots[number]] = []
		groups[roots[number]].append(number)
	for group: Array in groups.values():
		if group.size() < 3:
			continue
		for attempt in range(2 * group.size()):
			if rng.randf() >= 0.35:
				continue
			var a: int = group[rng.randi_range(0, group.size() - 1)]
			var b: int = group[rng.randi_range(0, group.size() - 1)]
			if a != b and not edges[a].has(b) and edges[a].size() < capacity[a] and edges[b].size() < capacity[b]:
				edges[a].append(b)
				edges[b].append(a)
	var rooms: Array = []
	for number in numbers:
		var doors: Array = []
		for target in edges[number]:
			doors.append({"kind": "room", "target": target})
		if number == entrance:
			doors.append({"kind": "entrance", "target": -1})
		if number == exit_room:
			doors.append({"kind": "exit", "target": -1})
		var walls := shuffled([0, 1, 2, 3], rng)
		for i in range(doors.size()):
			doors[i].wall = walls[i]
		rooms.append({"id": number, "doors": doors})
	return {"id": "generated-%d-%d" % [count, seed_value], "seed": str(seed_value),
		"title": "%d комнат" % count, "room_count": count, "path_percent": percent,
		"path_rooms": path_count, "entrance": entrance, "exit": exit_room, "rooms": rooms}
