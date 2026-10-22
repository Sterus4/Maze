extends Control

var active := false:
	set(value):
		active = value
		queue_redraw()

func _draw() -> void:
	var color := Color("77e6cf") if active else Color(1, 1, 1, 0.75)
	draw_arc(size * 0.5, 10, 0, TAU, 32, Color(0.03, 0.06, 0.09, 0.6), 4, true)
	draw_arc(size * 0.5, 8, 0, TAU, 32, color, 1.5, true)
	draw_circle(size * 0.5, 2, color)
