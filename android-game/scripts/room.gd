class_name MazeRoom
extends Node3D

var frames: Dictionary = {}
var accents: Dictionary = {}
var selected_wall := -1
var leaves: Dictionary = {}
var wall_nodes: Dictionary = {}
var colliders: Array[StaticBody3D] = []
var number := -1
const SPACING := 9.0
const TEAL := Color("77e6cf")
const GOLD := Color("ffcd88")

func material(color: Color, glow: bool = false) -> StandardMaterial3D:
	var result := StandardMaterial3D.new()
	result.albedo_color = color
	result.roughness = 0.9
	if glow:
		result.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	return result

func box(parent: Node3D, size: Vector3, point: Vector3, mat: Material) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	var geometry := BoxMesh.new()
	geometry.size = size
	mesh.mesh = geometry
	mesh.material_override = mat
	mesh.position = point
	parent.add_child(mesh)
	return mesh

func label(parent: Node3D, text: String, point: Vector3, color: Color, pixels: float = 0.005) -> void:
	var node := Label3D.new()
	node.text = text
	node.font_size = 64
	node.pixel_size = pixels
	node.modulate = color
	node.outline_size = 6
	node.outline_modulate = Color("101b2a")
	node.position = point
	parent.add_child(node)

func build(state: MazeState, room_number: int = -1) -> void:
	number = state.current if room_number < 0 else room_number
	var tint := Color.from_hsv(fmod(number * 0.137, 1.0), 0.16, 0.31)
	var wall_mat := material(tint)
	var trim := material(Color("24354a"))
	box(self, Vector3(9.2, 0.18, 9.2), Vector3(0, -0.09, 0), material(Color("172434")))
	box(self, Vector3(9.2, 0.15, 9.2), Vector3(0, 4.25, 0), material(Color("1c2b3d")))
	var grout := material(Color("26374a"))
	for i in range(-4, 5):
		box(self, Vector3(0.018, 0.012, 9), Vector3(i, 0.008, 0), grout)
		box(self, Vector3(9, 0.012, 0.018), Vector3(0, 0.008, i), grout)
	box(self, Vector3(2.0, 0.035, 0.5), Vector3(0, 4.13, 0), material(Color("d9f4ec"), true))
	var lamp := OmniLight3D.new()
	lamp.position = Vector3(0, 3.65, 0)
	lamp.light_color = Color("fff0d8")
	lamp.light_energy = 2.6
	lamp.omni_range = 7.0
	add_child(lamp)
	for wall in range(4):
		var anchor := Node3D.new()
		anchor.rotation.y = -wall * PI / 2
		add_child(anchor)
		wall_nodes[wall] = anchor
		var door: Dictionary = {}
		for candidate in state.rooms[number].doors:
			if int(candidate.wall) == wall:
				door = candidate
		box(anchor, Vector3(9, 0.08, 0.08), Vector3(0, 3.95, -4.37), trim)
		if door.is_empty():
			box(anchor, Vector3(9.15, 4.2, 0.18), Vector3(0, 2.1, -4.5), wall_mat)
			box(anchor, Vector3(9, 0.1, 0.08), Vector3(0, 0.15, -4.37), trim)
			label(anchor, "%02d" % number, Vector3(0, 2.1, -4.34), Color(tint.lightened(0.2)), 0.013)
			continue
		# A real opening: no full wall or solid frame behind the moving door.
		for side in [-1, 1]:
			box(anchor, Vector3(3.6, 4.2, 0.18), Vector3(side * 2.7, 2.1, -4.5), wall_mat)
			box(anchor, Vector3(3.5, 0.1, 0.08), Vector3(side * 2.7, 0.15, -4.37), trim)
		box(anchor, Vector3(1.8, 1.2, 0.18), Vector3(0, 3.6, -4.5), wall_mat)
		var color := TEAL
		var title := "КОМНАТА %d" % int(door.target)
		var subtitle := "НЕ ИССЛЕДОВАНА"
		if door.kind == "entrance":
			color = Color("91a5ba")
			title = "ВХОД"
			subtitle = "НАЧАЛО ПУТИ"
		elif door.kind == "exit":
			color = GOLD
			title = "ВЫХОД"
			subtitle = "СВОБОДА РЯДОМ"
		elif state.visited.has(int(door.target)):
			color = Color("b8a0e9")
			subtitle = "ВЫ УЖЕ БЫЛИ ЗДЕСЬ"
		var frame := material(color, true)
		frames[wall] = frame
		accents[wall] = color
		for side in [-1, 1]:
			box(anchor, Vector3(0.08, 3.04, 0.22), Vector3(side * 0.94, 1.52, -4.5), frame)
		box(anchor, Vector3(1.96, 0.08, 0.22), Vector3(0, 3.04, -4.5), frame)
		var hinge := Node3D.new()
		hinge.position = Vector3(-0.9, 0, -4.5)
		anchor.add_child(hinge)
		leaves[wall] = hinge
		box(hinge, Vector3(1.8, 2.98, 0.10), Vector3(0.9, 1.49, 0), material(Color("0e1826")))
		box(hinge, Vector3(0.03, 2.5, 0.025), Vector3(0.32, 1.45, 0.065), material(color.darkened(0.3), true))
		box(hinge, Vector3(0.10, 0.30, 0.08), Vector3(1.50, 1.40, 0.09), material(color, true))
		label(anchor, title, Vector3(0, 3.35, -4.26), color, 0.0045)
		label(hinge, subtitle, Vector3(0.9, 0.51, 0.075), color, 0.0020)
		label(hinge, str(int(door.target)) if door.kind == "room" else "→" if door.kind == "exit" else "•",
			Vector3(0.9, 1.95, 0.075), color, 0.009)
		var body := StaticBody3D.new()
		body.position = Vector3(0, 1.5, -4.15)
		body.set_meta("wall", wall)
		var shape := CollisionShape3D.new()
		var volume := BoxShape3D.new()
		volume.size = Vector3(1.95, 3.05, 0.25)
		shape.shape = volume
		body.add_child(shape)
		anchor.add_child(body)
		colliders.append(body)
	set_interactive(number == state.current)

func set_interactive(active: bool) -> void:
	for body in colliders:
		body.collision_layer = 1 if active else 0

func wall_direction(wall: int) -> Vector3:
	return global_basis * Vector3.FORWARD.rotated(Vector3.UP, -wall * PI / 2)

func build_exit() -> void:
	box(self, Vector3(9.2, 0.18, 9.2), Vector3(0, -0.09, 0), material(Color("41594e")))
	label(self, "ВЫХОД НАЙДЕН", Vector3(0, 2.2, -3), GOLD, 0.008)

func highlight(wall: int) -> void:
	if selected_wall == wall:
		return
	selected_wall = wall
	for index in frames:
		frames[index].albedo_color = Color.WHITE if index == wall else accents[index]
