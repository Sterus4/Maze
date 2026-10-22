extends Node3D
## A fixed viewpoint in one room. Doors follow graph links, not a global floor plan.

const State = preload("res://scripts/maze_state.gd")
const Room = preload("res://scripts/room.gd")
const Look = preload("res://scripts/look_controller.gd")
const Reticle = preload("res://scripts/reticle.gd")
const Generator = preload("res://scripts/maze_generator.gd")
const SAVE_PATH := "user://progress.json"
const INK := Color("101b2a")
const TEAL := Color("77e6cf")

var state := State.new()
var look := Look.new()
var catalog: Array = []
var camera: Camera3D
var room: MazeRoom
var neighbors: Dictionary = {}
var neighbor_back_walls: Dictionary = {}
var running := false
var transitioning := false
var selected_wall := -1
var touch_index := -1
var drag_start := Vector2.ZERO
var drag_distance := 0.0
var mouse_drag := false
var toast_generation := 0
var resumed_heading := 0.0

var hud: Control
var room_title: Label
var room_stats: Label
var target_title: Label
var instruction: Label
var top_row: BoxContainer
var top_panel: PanelContainer
var bottom_row: BoxContainer
var bottom_panel: PanelContainer
var menu_panel: PanelContainer
var orientation_button: Button
var orientation_mode := 0
var portrait_layout := false
var layout_initialized := false
var orientation_generation := 0
var orientation_settling := false
var enter_button: Button
var menu: Control
var menu_title: Label
var menu_text: Label
var room_count_input: LineEdit
var form_error: Label
var path_percent := 30
var path_percent_label: Label
var path_less: Button
var path_more: Button
var count_pad: Control
var pad_value: Label
var pad_fresh := true
var continue_button: Button
var reticle: Control
var toast: Label

func _ready() -> void:
	get_tree().auto_accept_quit = false
	var payload: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/mazes.json"))
	if not payload is Dictionary or int(payload.get("schema", -1)) != 1:
		push_error("Invalid maze catalog")
		get_tree().quit(1)
		return
	catalog = payload.get("mazes", [])
	if catalog.is_empty() or not state.load_maze(catalog[0]):
		push_error("No valid mazes found")
		get_tree().quit(1)
		return
	_build_world()
	_build_ui()
	look.setup()
	get_viewport().use_xr = false
	_load_display_settings()
	get_window().size_changed.connect(_update_layout)
	_update_layout()
	_load_saved()
	_rebuild_room()
	_show_menu()

func _build_world() -> void:
	var environment := WorldEnvironment.new()
	var settings := Environment.new()
	settings.background_mode = Environment.BG_COLOR
	settings.background_color = Color("182433")
	settings.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	settings.ambient_light_color = Color("d6e6f7")
	settings.ambient_light_energy = 0.65
	settings.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.environment = settings
	add_child(environment)
	camera = Camera3D.new()
	camera.position = Vector3(0, 1.65, 0)
	camera.fov = 78
	camera.near = 0.05
	camera.far = 25
	camera.current = true
	add_child(camera)

func _style(color: Color, border: Color = Color.TRANSPARENT) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(14)
	style.content_margin_left = 20
	style.content_margin_right = 20
	style.content_margin_top = 12
	style.content_margin_bottom = 12
	if border.a > 0:
		style.set_border_width_all(1)
		style.border_color = border
	return style

func _label(text: String, font_size: int, color: Color = Color("ecf2f9")) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label

func _button(text: String, callback: Callable, primary: bool = false) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size = Vector2(150, 54)
	button.add_theme_font_size_override("font_size", 20)
	button.add_theme_stylebox_override("normal", _style(TEAL if primary else Color("243448")))
	button.add_theme_stylebox_override("hover", _style(Color("a3eedc") if primary else Color("344c64")))
	button.add_theme_stylebox_override("pressed", _style(Color("58bca6")))
	button.add_theme_stylebox_override("disabled", _style(Color("26313e")))
	button.add_theme_color_override("font_color", INK if primary else Color.WHITE)
	button.add_theme_color_override("font_hover_color", INK if primary else Color.WHITE)
	button.add_theme_color_override("font_pressed_color", INK)
	button.add_theme_color_override("font_disabled_color", Color("8291a2"))
	button.focus_mode = Control.FOCUS_NONE
	button.pressed.connect(callback)
	return button

func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	hud = Control.new()
	hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(hud)
	var top := PanelContainer.new()
	top_panel = top
	top.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	top.offset_left = 22
	top.offset_top = 18
	top.offset_right = -22
	top.add_theme_stylebox_override("panel", _style(Color(0.04, 0.08, 0.13, 0.87)))
	hud.add_child(top)
	var row := BoxContainer.new()
	top_row = row
	row.add_theme_constant_override("separation", 12)
	top.add_child(row)
	var heading := VBoxContainer.new()
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(heading)
	room_title = _label("КОМНАТА", 25)
	heading.add_child(room_title)
	room_stats = _label("", 16, Color("b4c2d3"))
	room_stats.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	heading.add_child(room_stats)
	var controls := HBoxContainer.new()
	controls.add_theme_constant_override("separation", 12)
	row.add_child(controls)
	controls.add_child(_button("Центрировать", _recenter))
	controls.add_child(_button("Меню", _show_menu))
	var bottom := PanelContainer.new()
	bottom_panel = bottom
	bottom.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	bottom.offset_left = 22
	bottom.offset_right = -22
	bottom.offset_top = -106
	bottom.offset_bottom = -18
	bottom.add_theme_stylebox_override("panel", _style(Color(0.04, 0.08, 0.13, 0.9)))
	hud.add_child(bottom)
	var lower_row := BoxContainer.new()
	bottom_row = lower_row
	lower_row.add_theme_constant_override("separation", 20)
	bottom.add_child(lower_row)
	var target := VBoxContainer.new()
	target.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lower_row.add_child(target)
	target_title = _label("Посмотрите на дверь", 23, TEAL)
	target_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	target.add_child(target_title)
	instruction = _label("Проведите пальцем для обзора. Коснитесь двери для перехода.", 16)
	instruction.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	target.add_child(instruction)
	enter_button = _button("Перейти  →", func(): travel(selected_wall), true)
	enter_button.custom_minimum_size.x = 215
	lower_row.add_child(enter_button)
	reticle = Reticle.new()
	reticle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	reticle.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	hud.add_child(reticle)
	toast = _label("", 21, Color("ffdcaa"))
	toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	toast.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	toast.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	toast.offset_top = -163
	toast.offset_bottom = -118
	toast.offset_left = 22
	toast.offset_right = -22
	hud.add_child(toast)
	menu = Control.new()
	menu.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	layer.add_child(menu)
	var backdrop := ColorRect.new()
	backdrop.color = Color(0.025, 0.045, 0.075, 0.91)
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	menu.add_child(backdrop)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	menu.add_child(center)
	var panel := PanelContainer.new()
	menu_panel = panel
	panel.custom_minimum_size = Vector2(760, 0)
	panel.add_theme_stylebox_override("panel", _style(Color("142337"), Color("304b60")))
	center.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 15)
	panel.add_child(column)
	column.add_child(_label("MAZE  /  ROOMS", 18, TEAL))
	menu_title = _label("Найди выход", 44)
	column.add_child(menu_title)
	menu_text = _label("", 21)
	menu_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(menu_text)
	var counts := HBoxContainer.new()
	counts.add_theme_constant_override("separation", 14)
	column.add_child(counts)
	counts.add_child(_label("Комнат:", 22))
	room_count_input = LineEdit.new()
	room_count_input.text = "100"
	room_count_input.virtual_keyboard_type = LineEdit.KEYBOARD_TYPE_NUMBER
	room_count_input.virtual_keyboard_enabled = false
	room_count_input.editable = OS.get_name() != "Android"
	room_count_input.max_length = 5
	room_count_input.custom_minimum_size = Vector2(165, 56)
	room_count_input.add_theme_font_size_override("font_size", 25)
	room_count_input.text_submitted.connect(func(_text: String): _start_custom())
	room_count_input.text_changed.connect(func(_text: String): form_error.text = "От 1 до 5000 комнат")
	room_count_input.gui_input.connect(func(event: InputEvent):
		if (event is InputEventScreenTouch and event.pressed) or (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT):
			if OS.get_name() == "Android":
				_show_count_pad.call_deferred()
	)
	counts.add_child(room_count_input)
	for count in [12, 40, 100]:
		var preset := _button(str(count), _choose_count.bind(count))
		preset.custom_minimum_size.x = 100
		counts.add_child(preset)
	form_error = _label("От 1 до 5000 комнат", 17, Color("b5c6d8"))
	column.add_child(form_error)
	var path_row := HBoxContainer.new()
	path_row.add_theme_constant_override("separation", 14)
	column.add_child(path_row)
	var path_caption := _label("Кратчайший путь:", 22)
	path_caption.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	path_row.add_child(path_caption)
	path_less = _button("−10%", func(): _set_path_percent(path_percent - 10))
	path_less.custom_minimum_size.x = 100
	path_row.add_child(path_less)
	path_percent_label = _label("", 26, TEAL)
	path_percent_label.custom_minimum_size.x = 70
	path_percent_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	path_row.add_child(path_percent_label)
	path_more = _button("+10%", func(): _set_path_percent(path_percent + 10))
	path_more.custom_minimum_size.x = 100
	path_row.add_child(path_more)
	_set_path_percent(30)
	orientation_button = _button("", func(): _set_orientation_mode((orientation_mode + 1) % 3))
	column.add_child(orientation_button)
	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 14)
	column.add_child(buttons)
	var start := _button("Новый лабиринт", _start_custom, true)
	start.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	buttons.add_child(start)
	continue_button = _button("Продолжить", _continue_game)
	continue_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	buttons.add_child(continue_button)
	for text in ["Поворот телефона или движение пальцем — обзор на 360°.", "Касание двери — переход. Золотая дверь — выход."]:
		var help := _label(text, 18, Color("b5c6d8"))
		help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		column.add_child(help)
	if OS.get_name() != "Android":
		var help := _label("На компьютере: мышь или стрелки, Enter — пройти.", 17, Color("8fa4ba"))
		help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		column.add_child(help)
	_build_count_pad(layer)

func _set_orientation_mode(mode: int, persist: bool = true) -> void:
	orientation_mode = clampi(mode, 0, 2)
	orientation_button.text = "Экран: " + ["Авто", "Горизонтально", "Вертикально"][orientation_mode] + "  ↻"
	if OS.get_name() == "Android":
		var modes := [DisplayServer.SCREEN_SENSOR, DisplayServer.SCREEN_SENSOR_LANDSCAPE, DisplayServer.SCREEN_PORTRAIT]
		DisplayServer.screen_set_orientation(modes[orientation_mode])
	elif orientation_mode != 0:
		get_window().size = Vector2i(648, 1152) if orientation_mode == 2 else Vector2i(1152, 648)
	if persist:
		var settings := ConfigFile.new()
		settings.set_value("display", "orientation", orientation_mode)
		settings.save("user://display.cfg")

func _load_display_settings() -> void:
	var settings := ConfigFile.new()
	settings.load("user://display.cfg")
	_set_orientation_mode(int(settings.get_value("display", "orientation", 0)), false)

func _update_layout() -> void:
	var portrait := get_window().size.y > get_window().size.x
	if layout_initialized and portrait == portrait_layout:
		return
	portrait_layout = portrait
	layout_initialized = true
	get_window().content_scale_size = Vector2i(720, 1280) if portrait else Vector2i(1280, 720)
	top_row.vertical = portrait
	top_panel.offset_bottom = 0
	bottom_row.vertical = portrait
	menu_panel.custom_minimum_size.x = 680 if portrait else 760
	bottom_panel.offset_top = -205 if portrait else -106
	toast.offset_top = -285 if portrait else -163
	toast.offset_bottom = -217 if portrait else -118
	touch_index = -1
	mouse_drag = false
	# Android changes sensor axes with the display. Calibrate after fresh samples.
	if look.enabled:
		orientation_generation += 1
		var generation := orientation_generation
		var preserved := Quaternion.from_euler(Vector3(camera.rotation.x, camera.rotation.y, 0))
		orientation_settling = true
		get_tree().create_timer(0.4).timeout.connect(func():
			if generation != orientation_generation:
				return
			if not transitioning:
				look.manual = preserved
				look.offset = (preserved * look.sensor_rotation().inverse()).normalized()
				camera.quaternion = preserved
			orientation_settling = false
		)

func _build_count_pad(layer: CanvasLayer) -> void:
	count_pad = Control.new()
	count_pad.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	layer.add_child(count_pad)
	var backdrop := ColorRect.new()
	backdrop.color = Color(0.025, 0.045, 0.075, 0.98)
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	count_pad.add_child(backdrop)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	count_pad.add_child(center)
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _style(Color("142337")))
	center.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	panel.add_child(column)
	column.add_child(_label("Сколько комнат?", 28))
	column.add_child(_label("Введите число от 1 до 5000", 18, Color("b5c6d8")))
	pad_value = _label("", 40, TEAL)
	pad_value.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(pad_value)
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 10)
	grid.add_theme_constant_override("v_separation", 10)
	column.add_child(grid)
	for key in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "⌫"]:
		var button := _button(key, _pad_key.bind(key))
		button.custom_minimum_size = Vector2(112, 58)
		grid.add_child(button)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 12)
	column.add_child(actions)
	var cancel := _button("Отмена", func(): count_pad.hide())
	cancel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	actions.add_child(cancel)
	var done := _button("Готово", func():
		room_count_input.text = pad_value.text
		room_count_input.release_focus()
		form_error.text = "От 1 до 5000 комнат"
		count_pad.hide(), true)
	done.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	actions.add_child(done)
	count_pad.hide()

func _show_count_pad() -> void:
	if not menu.visible or count_pad.visible:
		return
	pad_value.text = room_count_input.text
	pad_fresh = true
	count_pad.show()

func _pad_key(key: String) -> void:
	if key == "C":
		pad_value.text = ""
	elif key == "⌫":
		pad_value.text = pad_value.text.left(maxi(0, pad_value.text.length() - 1))
	else:
		if pad_fresh:
			pad_value.text = ""
		if pad_value.text.length() < 5:
			pad_value.text += key
	pad_fresh = false

func _choose_count(count: int) -> void:
	room_count_input.text = str(count)
	room_count_input.release_focus()
	if DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD):
		DisplayServer.virtual_keyboard_hide()
	form_error.text = "От 1 до 5000 комнат"

func _set_path_percent(value: int) -> void:
	path_percent = clampi(int(round(value / 10.0)) * 10, 10, 90)
	path_percent_label.text = "%d%%" % path_percent
	path_less.disabled = path_percent == 10
	path_more.disabled = path_percent == 90

func _start_custom() -> void:
	var text := room_count_input.text.strip_edges()
	if not text.is_valid_int() or int(text) < 1 or int(text) > Generator.MAX_ROOMS:
		form_error.text = "Введите целое число от 1 до 5000."
		return
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	var data := Generator.generate(int(text), rng.randi(), path_percent)
	if not state.load_maze(data):
		form_error.text = "Не удалось создать лабиринт. Попробуйте ещё раз."
		return
	_begin_game()

func start_maze(index: int) -> void:
	if index < 0 or index >= catalog.size() or not state.load_maze(catalog[index]):
		return
	_begin_game()

func _begin_game() -> void:
	room_count_input.release_focus()
	if DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD):
		DisplayServer.virtual_keyboard_hide()
	running = true
	menu.hide()
	hud.show()
	_rebuild_room()
	_save()
	_show_toast("Осмотритесь: выход может оказаться за спиной.")

func _continue_game() -> void:
	if state.finished:
		return
	menu.hide()
	hud.show()
	running = true
	_recenter()

func _show_menu() -> void:
	if transitioning:
		return
	running = false
	touch_index = -1
	mouse_drag = false
	hud.hide()
	menu.show()
	continue_button.disabled = state.finished
	menu_title.text = "Вы выбрались!" if state.finished else "Найди выход"
	menu_text.text = "Переходов: %d · посещено: %d / %d" % [state.moves, state.visited.size(), state.rooms.size()] if state.finished else "Ты в центре комнаты. Осмотрись и выбери дверь.\nКаждый переход приближает к выходу — или ведёт в тупик."

func _clear_neighbors(keep: MazeRoom = null) -> void:
	for neighbor: MazeRoom in neighbors.values():
		if neighbor != keep:
			remove_child(neighbor)
			neighbor.queue_free()
	neighbors.clear()
	neighbor_back_walls.clear()

func _prepare_neighbors() -> void:
	# Only one hop is materialized. Closed doors hide inconsistent global geometry.
	for door in state.rooms[state.current].doors:
		if door.kind == "entrance":
			continue
		var wall := int(door.wall)
		var adjacent := Room.new()
		add_child(adjacent)
		adjacent.position = room.position + room.wall_direction(wall) * Room.SPACING
		if door.kind == "exit":
			adjacent.rotation.y = room.rotation.y - wall * PI / 2
			adjacent.build_exit()
		else:
			var back := -1
			for candidate in state.rooms[int(door.target)].doors:
				if candidate.kind == "room" and int(candidate.target) == state.current:
					back = int(candidate.wall)
			# Opposing door normals and coincident thresholds, for every wall pair.
			adjacent.rotation.y = room.rotation.y + (back - wall) * PI / 2 + PI
			adjacent.build(state, int(door.target))
			adjacent.set_interactive(false)
			# Both rooms share this boundary. Draw only the current room's wall/door.
			adjacent.wall_nodes[back].hide()
			neighbor_back_walls[wall] = back
		neighbors[wall] = adjacent

func _rebuild_room() -> void:
	_clear_neighbors()
	if is_instance_valid(room):
		remove_child(room)
		room.queue_free()
	room = Room.new()
	add_child(room)
	room.build(state)
	camera.position = Vector3(0, 1.65, 0)
	var heading := 0.0
	for door in state.rooms[state.current].doors:
		if door.kind == "room" or door.kind == "exit":
			heading = -int(door.wall) * PI / 2
	look.recenter(heading)
	resumed_heading = heading
	camera.quaternion = look.orientation(0)
	_prepare_neighbors()
	_refresh_room_hud()

func _refresh_room_hud() -> void:
	room_title.text = "КОМНАТА  %02d" % state.current
	room_stats.text = "Посещено %d / %d  ·  переходов %d  ·  дверей %d" % [state.visited.size(), state.rooms.size(), state.moves, state.rooms[state.current].doors.size()]
	_select(-1)

func pick_wall(screen_point: Vector2) -> int:
	var origin := camera.project_ray_origin(screen_point)
	var ray := camera.project_ray_normal(screen_point)
	var query := PhysicsRayQueryParameters3D.create(origin, origin + ray * 12)
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if not hit.is_empty() and hit.collider.has_meta("wall"):
		return int(hit.collider.get_meta("wall"))
	return -1

func _select(wall: int) -> void:
	selected_wall = wall
	room.highlight(wall)
	reticle.set("active", wall >= 0)
	var door := state.door_on_wall(wall)
	enter_button.disabled = door.is_empty() or transitioning or door.kind == "entrance"
	if door.is_empty():
		target_title.text = "Посмотрите на дверь"
	elif door.kind == "entrance":
		target_title.text = "Это вход. Найдите другой выход."
	elif door.kind == "exit":
		target_title.text = "Выход из лабиринта"
	else:
		target_title.text = "Комната %d%s" % [int(door.target), " · уже посещена" if state.visited.has(int(door.target)) else ""]

func travel(wall: int) -> void:
	if not running or transitioning:
		return
	var door := state.door_on_wall(wall)
	if door.is_empty():
		return
	if door.kind == "entrance":
		_show_toast("Здесь вы вошли. Выход находится в другой двери.")
		return
	transitioning = true
	hud.hide()
	touch_index = -1
	mouse_drag = false
	var next_room: MazeRoom = neighbors[wall]
	var direction := room.wall_direction(wall)
	var heading := atan2(-direction.x, -direction.z)
	var facing := Quaternion(Vector3.UP, heading)
	var start_rotation := camera.quaternion
	var align := create_tween()
	align.tween_method(func(t: float): camera.quaternion = start_rotation.slerp(facing, t), 0.0, 1.0, 0.2)
	await align.finished
	var hinge: Node3D = room.leaves[wall]
	var opening := create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	opening.tween_property(hinge, "rotation:y", -PI * 0.56, 0.38)
	await opening.finished
	var walk := create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	walk.tween_property(camera, "position", next_room.position + Vector3(0, 1.65, 0), 1.35)
	await walk.finished
	var closing := create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	closing.tween_property(hinge, "rotation:y", 0.0, 0.3)
	await closing.finished
	var result := state.enter(wall)
	if result == "moved":
		next_room.wall_nodes[neighbor_back_walls[wall]].show()
		_clear_neighbors(next_room)
		remove_child(room)
		room.queue_free()
		room = next_room
		# Rebase at the center, without changing any visible relative transforms.
		room.position = Vector3.ZERO
		camera.position = Vector3(0, 1.65, 0)
		room.set_interactive(true)
		_prepare_neighbors()
	look.recenter(heading)
	resumed_heading = heading
	camera.quaternion = facing
	_save()
	transitioning = false
	_refresh_room_hud()
	if result == "won":
		_show_menu()
	else:
		hud.show()

func _process(delta: float) -> void:
	if not is_instance_valid(camera):
		return
	var orientation := look.orientation(delta)
	if not running or transitioning or orientation_settling:
		return
	var arrow := Vector2(float(Input.is_physical_key_pressed(KEY_RIGHT)) - float(Input.is_physical_key_pressed(KEY_LEFT)),
		float(Input.is_physical_key_pressed(KEY_DOWN)) - float(Input.is_physical_key_pressed(KEY_UP)))
	if not arrow.is_zero_approx():
		look.drag(arrow * delta * 260)
		orientation = look.orientation(0)
	camera.quaternion = orientation
	instruction.text = "Поверните телефон или проведите пальцем. Коснитесь двери." if look.enabled else "Проведите пальцем для обзора. Коснитесь двери для перехода."
	if look.enabled and not look.gyro_seen and look.waiting_seconds > 8:
		instruction.text = "Поверните телефон для проверки датчика. Обзор пальцем доступен всегда."

func _physics_process(_delta: float) -> void:
	if running and not transitioning:
		_select(pick_wall(get_viewport().get_visible_rect().size * 0.5))

func _input(event: InputEvent) -> void:
	if event is InputEventMouse and event.device == InputEvent.DEVICE_ID_EMULATION:
		return
	# Finish a gesture even if it ends over a UI panel that consumes input.
	if event is InputEventScreenDrag and event.index == touch_index:
		drag_distance += event.relative.length()
		look.drag(event.relative)
		get_viewport().set_input_as_handled()
	elif event is InputEventScreenTouch and not event.pressed and event.index == touch_index:
		touch_index = -1
		if not event.canceled and drag_distance < 14 and event.position.distance_to(drag_start) < 14:
			travel(pick_wall(event.position))
		get_viewport().set_input_as_handled()
	elif event is InputEventMouseMotion and mouse_drag:
		drag_distance += event.relative.length()
		look.drag(event.relative)
		get_viewport().set_input_as_handled()
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed and mouse_drag:
		mouse_drag = false
		if drag_distance < 14 and event.position.distance_to(drag_start) < 14:
			travel(pick_wall(event.position))
		get_viewport().set_input_as_handled()

func _unhandled_input(event: InputEvent) -> void:
	if transitioning or (event is InputEventMouse and event.device == InputEvent.DEVICE_ID_EMULATION):
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE:
			if menu.visible:
				_continue_game()
			else:
				_show_menu()
		elif event.keycode == KEY_ENTER and running:
			travel(selected_wall)
		elif event.keycode == KEY_C and running:
			_recenter()
	if not running or transitioning:
		return
	if event is InputEventScreenTouch:
		if event.pressed and touch_index == -1:
			touch_index = event.index
			drag_start = event.position
			drag_distance = 0
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		mouse_drag = true
		drag_start = event.position
		drag_distance = 0

func _recenter() -> void:
	if transitioning:
		return
	look.recenter(resumed_heading)
	_show_toast("Взгляд центрирован. Держите телефон перед собой.")

func _show_toast(text: String) -> void:
	toast_generation += 1
	var generation := toast_generation
	toast.text = text
	get_tree().create_timer(4.0).timeout.connect(func():
		if generation == toast_generation:
			toast.text = ""
	)

func _save() -> void:
	if state.rooms.is_empty():
		return
	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file != null:
		var saved := state.snapshot()
		saved.maze = state.data
		file.store_string(JSON.stringify(saved))

func _load_saved() -> void:
	if not FileAccess.file_exists(SAVE_PATH):
		return
	var parser := JSON.new()
	if parser.parse(FileAccess.get_file_as_string(SAVE_PATH)) != OK:
		return
	var saved: Variant = parser.data
	if not saved is Dictionary:
		return
	if saved.get("maze") is Dictionary:
		var restored := State.new()
		if restored.load_maze(saved.maze) and restored.restore(saved):
			state = restored
			room_count_input.text = str(state.rooms.size())
			_set_path_percent(int(state.data.get("path_percent", 30)))
		return
	for index in range(catalog.size()):
		if str(catalog[index].id) == str(saved.get("maze_id", "")):
			if state.load_maze(catalog[index]):
				state.restore(saved)
				room_count_input.text = str(state.rooms.size())
				_set_path_percent(int(state.data.get("path_percent", 30)))
			return

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_PAUSED or what == NOTIFICATION_WM_CLOSE_REQUEST:
		_save()
		touch_index = -1
		mouse_drag = false
		if what == NOTIFICATION_WM_CLOSE_REQUEST:
			get_tree().quit()
	elif what == NOTIFICATION_WM_GO_BACK_REQUEST:
		if count_pad.visible:
			count_pad.hide()
		elif menu.visible and room_count_input.has_focus():
			room_count_input.release_focus()
			if DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD):
				DisplayServer.virtual_keyboard_hide()
		elif running:
			_show_menu()
		else:
			_save()
			get_tree().quit()
	elif what == NOTIFICATION_APPLICATION_RESUMED and is_instance_valid(camera):
		# Sensors resume asynchronously. Preserve the view once fresh samples arrive.
		var preserved := camera.quaternion
		get_tree().create_timer(0.25).timeout.connect(func():
			look.manual = preserved
			look.offset = (preserved * look.sensor_rotation().inverse()).normalized()
		)

func _exit_tree() -> void:
	look.shutdown()
