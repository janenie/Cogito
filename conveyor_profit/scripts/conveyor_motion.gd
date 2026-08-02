class_name ConveyorMotion
extends RefCounted


static func advance(progress: float, speed: float, delta: float, path_length: float) -> float:
	if path_length <= 0.0:
		return 0.0
	return wrapf(progress + speed * delta, 0.0, path_length)
