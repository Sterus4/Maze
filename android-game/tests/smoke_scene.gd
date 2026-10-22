extends SceneTree
## Runs the real scene, checks door picking/transition, and exports preview PNGs.

var failures := 0
func expect(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		printerr("FAIL: " + message)

func _initialize() -> void:
	call_deferred("run_test")

func run_test() -> void:
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	await process_frame
	await process_frame
	var original_save: String = FileAccess.get_file_as_string("user://progress.json") if FileAccess.file_exists("user://progress.json") else ""
	game.start_maze(0)
	await physics_frame
	await process_frame
	await process_frame
	var wall: int = game.pick_wall(root.get_visible_rect().size * 0.5)
	expect(wall >= 0, "center ray hits a door")
	var old_room: int = game.state.current
	var door: Dictionary = game.state.door_on_wall(wall)
	expect(door.get("kind") == "room", "initial view faces a room door")
	await capture("room-preview.png")
	var preloaded = game.neighbors[wall]
	var old_center: Vector3 = game.camera.position
	game.travel(wall)
	await create_timer(1.15).timeout
	expect(game.transitioning, "transition remains active while walking")
	expect(game.camera.position.distance_to(old_center) > 1.0, "camera physically moves through doorway")
	expect(absf(game.room.leaves[wall].rotation.y) > 1.0, "door leaf opens")
	expect(game.state.moves == 0, "move committed only after passage completes")
	await capture("walk-preview.png")
	while game.transitioning:
		await process_frame
	expect(game.room == preloaded, "preloaded neighbor is reused")
	expect(game.state.current == int(door.target), "transition arrives in target room")
	expect(game.state.moves == 1, "one transition is one move")
	expect(game.camera.position.is_equal_approx(Vector3(0, 1.65, 0)), "camera stays in center")
	var back := -1
	for candidate in game.state.rooms[game.state.current].doors:
		if candidate.kind == "room" and int(candidate.target) == old_room:
			back = int(candidate.wall)
	expect(back >= 0, "return door exists in scene")
	await game.travel(back)
	expect(game.state.current == old_room and game.state.moves == 2, "return traversal works")
	game._show_menu()
	game._choose_count(40)
	game._start_custom()
	expect(game.state.rooms.size() == 40, "40-room preset generates 40 rooms")
	game._show_menu()
	game._choose_count(100)
	game._set_path_percent(0)
	expect(game.path_percent == 10 and game.path_less.disabled, "minimum selectable path is 10 percent")
	game._set_path_percent(100)
	expect(game.path_percent == 90 and game.path_more.disabled, "maximum selectable path is 90 percent")
	game.path_less.pressed.emit()
	game.path_less.pressed.emit()
	expect(game.path_percent == 70, "percentage buttons change value in tens")
	game._start_custom()
	expect(game.state.rooms.size() == 100, "100-room preset generates 100 rooms")
	expect(int(game.state.data.path_rooms) == 70, "selected percentage reaches generator")
	game._show_menu()
	game.room_count_input.text = "37"
	game._start_custom()
	expect(game.state.rooms.size() == 37, "typed custom room count")
	var saved_data: Dictionary = game.state.data.duplicate(true)
	game.start_maze(0)
	# start_maze writes its own save; restore the generated graph's persisted payload.
	var saved_file := FileAccess.open("user://progress.json", FileAccess.WRITE)
	saved_file.store_string(JSON.stringify({"maze": saved_data, "maze_id": saved_data.id,
		"seed": saved_data.seed, "current": saved_data.entrance, "visited": [saved_data.entrance], "moves": 0, "finished": false}))
	saved_file.close()
	game._load_saved()
	expect(game.path_percent == 70, "path percentage restored from saved maze")
	expect(str(game.state.data.id) == str(saved_data.id) and str(game.state.data.seed) == str(saved_data.seed), "custom maze identity survives save reload")
	expect(game.state.rooms.size() == int(saved_data.room_count), "custom maze size survives save reload")
	for saved_room in saved_data.rooms:
		var restored_room: Dictionary = game.state.rooms[int(saved_room.id)]
		expect(restored_room.doors.size() == saved_room.doors.size(), "saved door count")
		for i in range(saved_room.doors.size()):
			var before: Dictionary = saved_room.doors[i]
			var after: Dictionary = restored_room.doors[i]
			expect(before.kind == after.kind and int(before.target) == int(after.target) and int(before.wall) == int(after.wall), "saved connections and wall positions")
	game._rebuild_room()
	game._show_menu()
	game.room_count_input.text = "0"
	game._start_custom()
	expect(game.menu.visible and game.state.rooms.size() == 37, "invalid count leaves existing game intact")
	game._choose_count(37)
	await process_frame
	await capture("menu-preview.png")
	var landscape_size := root.size
	root.size = Vector2i(648, 1152)
	for frame in range(4):
		await process_frame
	expect(game.portrait_layout and game.top_row.vertical and game.bottom_row.vertical, "portrait rearranges HUD")
	var screen := root.get_visible_rect()
	for control in [game.menu_panel, game.orientation_button, game.room_count_input, game.path_more, game.continue_button]:
		expect(screen.encloses(control.get_global_rect()), "portrait menu controls fit screen")
	await capture("portrait-menu-preview.png")
	game._continue_game()
	for frame in range(4):
		await process_frame
	for control in [game.top_panel, game.bottom_panel, game.enter_button, game.instruction]:
		expect(screen.encloses(control.get_global_rect()), "portrait HUD fits screen")
	await capture("portrait-room-preview.png")
	root.size = landscape_size
	for frame in range(4):
		await process_frame
	expect(not game.portrait_layout and not game.top_row.vertical, "landscape layout restores")
	game._show_menu()
	game._choose_count(1)
	game._start_custom()
	var exit_wall := -1
	for candidate in game.state.rooms[game.state.current].doors:
		if candidate.kind == "exit":
			exit_wall = int(candidate.wall)
	await game.travel(exit_wall)
	expect(game.state.finished and game.menu.visible, "animated exit opens victory menu")
	expect(game.state.moves == 0, "exit does not add a room transition")
	game.queue_free()
	await process_frame
	var restore := FileAccess.open("user://progress.json", FileAccess.WRITE)
	if restore != null:
		restore.store_string(original_save)
	print("Scene smoke: %d failures" % failures)
	quit(0 if failures == 0 else 1)

func capture(filename: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	var target := ProjectSettings.globalize_path("res://../build/" + filename)
	var error := root.get_texture().get_image().save_png(target)
	expect(error == OK, "preview PNG saved")
