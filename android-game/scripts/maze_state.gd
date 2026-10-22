class_name MazeState
extends RefCounted
## Pure graph and game state. No rendering, sensors, or Android dependency.

var data: Dictionary
var rooms: Dictionary = {}
var current: int = -1
var visited: Dictionary = {}
var moves: int = 0
var finished: bool = false

func load_maze(source: Dictionary) -> bool:
	if not source.has_all(["id", "entrance", "exit", "rooms", "room_count"]):
		return false
	var parsed: Dictionary = {}
	for room in source.rooms:
		var number := int(room.get("id", -1))
		if number < 1 or parsed.has(number) or not room.has("doors"):
			return false
		if room.doors.is_empty() or room.doors.size() > 4:
			return false
		var used: Dictionary = {}
		var targets: Dictionary = {}
		for door in room.doors:
			if not door.has_all(["kind", "target", "wall"]):
				return false
			var wall := int(door.wall)
			if wall < 0 or wall > 3 or used.has(wall):
				return false
			used[wall] = true
			if door.kind not in ["room", "entrance", "exit"]:
				return false
			if door.kind == "room":
				var target := int(door.target)
				if target == number or targets.has(target):
					return false
				targets[target] = true
		parsed[number] = room
	if parsed.size() != int(source.room_count) or not parsed.has(int(source.entrance)) or not parsed.has(int(source.exit)):
		return false
	var entrances := 0
	var exits := 0
	for number in parsed:
		for door in parsed[number].doors:
			if door.kind == "room":
				var target := int(door.target)
				if not parsed.has(target):
					return false
				var reciprocal := false
				for back in parsed[target].doors:
					if back.kind == "room" and int(back.target) == number:
						reciprocal = true
				if not reciprocal:
					return false
			elif door.kind == "entrance":
				entrances += 1
				if number != int(source.entrance):
					return false
			elif door.kind == "exit":
				exits += 1
				if number != int(source.exit):
					return false
	if entrances != 1 or exits != 1:
		return false
	var reached := {int(source.entrance): true}
	var pending := [int(source.entrance)]
	while not pending.is_empty():
		var number: int = pending.pop_back()
		for door in parsed[number].doors:
			if door.kind == "room" and not reached.has(int(door.target)):
				reached[int(door.target)] = true
				pending.append(int(door.target))
	if reached.size() != parsed.size():
		return false
	data = source
	rooms = parsed
	current = int(source.entrance)
	visited = {current: true}
	moves = 0
	finished = false
	return true

func door_on_wall(wall: int) -> Dictionary:
	for door in rooms[current].doors:
		if int(door.wall) == wall:
			return door
	return {}

func enter(wall: int) -> String:
	if finished:
		return "finished"
	var door := door_on_wall(wall)
	if door.is_empty():
		return "invalid"
	if door.kind == "entrance":
		return "entrance"
	if door.kind == "exit":
		finished = true
		return "won"
	current = int(door.target)
	visited[current] = true
	moves += 1
	return "moved"

func snapshot() -> Dictionary:
	return {"maze_id": data.id, "seed": str(data.seed), "current": current,
		"visited": visited.keys(), "moves": moves, "finished": finished}

func restore(saved: Dictionary) -> bool:
	if str(saved.get("maze_id", "")) != str(data.id) or str(saved.get("seed", "")) != str(data.seed):
		return false
	var destination := int(saved.get("current", -1))
	if not rooms.has(destination) or int(saved.get("moves", -1)) < 0:
		return false
	var seen: Dictionary = {}
	for number in saved.get("visited", []):
		if not rooms.has(int(number)):
			return false
		seen[int(number)] = true
	if not seen.has(destination) or not seen.has(int(data.entrance)):
		return false
	if bool(saved.get("finished", false)) and destination != int(data.exit):
		return false
	current = destination
	visited = seen
	moves = int(saved.moves)
	finished = bool(saved.get("finished", false))
	return true
