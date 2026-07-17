extends CogitoStaticInteractable

signal watered

@export var hint_text: String = "You watered the flowers."

func interact(interactor: Node3D) -> void:
	watered.emit()
	if interactor.has_method("send_hint"):
		interactor.send_hint(null, hint_text)
