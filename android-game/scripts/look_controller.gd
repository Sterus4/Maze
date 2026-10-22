class_name RoomLook
extends RefCounted
## Use the engine's gyro/gravity fusion, but keep a single ordinary Camera3D.
## No headset, camera permission, positional tracking or stereo viewport.

var sensor: XRInterface
var enabled := false
var offset := Quaternion.IDENTITY
var manual := Quaternion.IDENTITY
var gyro_seen := false
var waiting_seconds := 0.0

func setup() -> void:
	if OS.get_name() == "Android":
		sensor = XRServer.find_interface("Native mobile")
		if sensor != null:
			enabled = sensor.initialize()
			if enabled:
				sensor.set("eye_height", 0.0)
				sensor.set("iod", 0.0)

func sensor_rotation() -> Quaternion:
	if sensor != null and sensor.is_initialized():
		return sensor.get_transform_for_view(0, Transform3D.IDENTITY).basis.orthonormalized().get_rotation_quaternion()
	return Quaternion.IDENTITY

func orientation(delta: float) -> Quaternion:
	if enabled:
		waiting_seconds += delta
		if Input.get_gyroscope().length() > 0.1:
			gyro_seen = true
		return (offset * sensor_rotation()).normalized()
	return manual

func recenter(yaw: float = 0.0) -> void:
	manual = Quaternion(Vector3.UP, yaw)
	offset = (manual * sensor_rotation().inverse()).normalized()

func drag(relative: Vector2) -> void:
	# Dragging moves the scene with the finger. Keep the horizon level in touch mode.
	var current := orientation(0.0)
	var euler := current.get_euler()
	var yaw := euler.y - relative.x * 0.004
	var pitch := clampf(euler.x - relative.y * 0.004, -PI * 0.49, PI * 0.49)
	manual = Quaternion.from_euler(Vector3(pitch, yaw, 0.0))
	offset = (manual * sensor_rotation().inverse()).normalized()

func shutdown() -> void:
	if sensor != null and sensor.is_initialized():
		sensor.uninitialize()
