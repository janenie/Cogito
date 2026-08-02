class_name FixedWindowDecks
extends RefCounted

const CARROT_CORN := {
	"ingredients": ["sausage", "avocado", "onion", "mushroom", "onion", "cheese", "bacon", "tomato", "tomato", "cheese", "corn", "cheese", "carrot", "meat", "tomato", "egg"],
	"decoy_recipe_id": "avocado_burger",
}
const BROCCOLI_CORN := {
	"ingredients": ["bacon", "avocado", "sausage", "corn", "broccoli", "cheese", "mushroom", "broccoli", "bacon", "pumpkin", "cheese", "mushroom", "meat", "tomato", "egg", "egg"],
	"decoy_recipe_id": "avocado_burger",
}
const AVOCADO_SALAD_CORN := {
	"ingredients": ["lettuce", "meat", "cheese", "fish", "fish", "lettuce", "avocado", "fish", "tomato", "bacon", "corn", "corn", "mushroom", "fish", "egg", "cheese"],
	"decoy_recipe_id": "avocado_burger",
}
const CARROT_PUMPKIN := {
	"ingredients": ["meat", "carrot", "sausage", "onion", "pumpkin", "tomato", "mushroom", "onion", "mushroom", "onion", "mushroom", "onion", "corn", "bread", "sausage", "mushroom"],
	"decoy_recipe_id": "avocado_burger",
}
const BROCCOLI_PUMPKIN := {
	"ingredients": ["onion", "lettuce", "broccoli", "tomato", "cheese", "onion", "sausage", "meat", "egg", "bacon", "mushroom", "egg", "pumpkin", "bacon", "mushroom", "lettuce"],
	"decoy_recipe_id": "corn_bacon_omelet",
}
const AVOCADO_SALAD_PUMPKIN := {
	"ingredients": ["broccoli", "lettuce", "pumpkin", "mushroom", "bacon", "corn", "cheese", "sausage", "sausage", "mushroom", "onion", "onion", "sausage", "tomato", "tomato", "avocado"],
	"decoy_recipe_id": "corn_bacon_omelet",
}
const CARROT_AVOCADO_FISH_A := {
	"ingredients": ["egg", "egg", "carrot", "avocado", "egg", "mushroom", "fish", "sausage", "meat", "corn", "sausage", "bacon", "onion", "bread", "onion", "fish"],
	"decoy_recipe_id": "avocado_burger",
}
const BROCCOLI_AVOCADO_FISH_A := {
	"ingredients": ["bread", "bread", "egg", "cheese", "onion", "bread", "broccoli", "onion", "bacon", "broccoli", "pumpkin", "bacon", "fish", "avocado", "fish", "tomato"],
	"decoy_recipe_id": "avocado_burger",
}
const CARROT_AVOCADO_FISH_B := {
	"ingredients": ["sausage", "sausage", "carrot", "avocado", "egg", "mushroom", "fish", "egg", "meat", "corn", "carrot", "bacon", "onion", "bread", "onion", "fish"],
	"decoy_recipe_id": "avocado_burger",
}
const BROCCOLI_AVOCADO_FISH_B := {
	"ingredients": ["bread", "egg", "egg", "cheese", "onion", "bread", "broccoli", "onion", "bacon", "broccoli", "pumpkin", "bacon", "fish", "avocado", "fish", "tomato"],
	"decoy_recipe_id": "avocado_burger",
}

const DECKS: Array[Dictionary] = [
	{"id": "A", "windows": [CARROT_CORN, CARROT_PUMPKIN, BROCCOLI_CORN, BROCCOLI_PUMPKIN, AVOCADO_SALAD_CORN, AVOCADO_SALAD_PUMPKIN, CARROT_AVOCADO_FISH_A, BROCCOLI_AVOCADO_FISH_A, CARROT_AVOCADO_FISH_B, BROCCOLI_AVOCADO_FISH_B]},
	{"id": "B", "windows": [CARROT_PUMPKIN, CARROT_CORN, BROCCOLI_PUMPKIN, BROCCOLI_CORN, AVOCADO_SALAD_PUMPKIN, AVOCADO_SALAD_CORN, BROCCOLI_AVOCADO_FISH_A, CARROT_AVOCADO_FISH_A, BROCCOLI_AVOCADO_FISH_B, CARROT_AVOCADO_FISH_B]},
	{"id": "C", "windows": [CARROT_CORN, BROCCOLI_CORN, CARROT_PUMPKIN, BROCCOLI_PUMPKIN, AVOCADO_SALAD_CORN, CARROT_AVOCADO_FISH_A, AVOCADO_SALAD_PUMPKIN, BROCCOLI_AVOCADO_FISH_A, CARROT_AVOCADO_FISH_B, BROCCOLI_AVOCADO_FISH_B]},
	{"id": "D", "windows": [CARROT_PUMPKIN, BROCCOLI_PUMPKIN, CARROT_CORN, BROCCOLI_CORN, CARROT_AVOCADO_FISH_A, AVOCADO_SALAD_PUMPKIN, AVOCADO_SALAD_CORN, BROCCOLI_AVOCADO_FISH_A, BROCCOLI_AVOCADO_FISH_B, CARROT_AVOCADO_FISH_B]},
	{"id": "E", "windows": [CARROT_CORN, CARROT_PUMPKIN, CARROT_AVOCADO_FISH_A, BROCCOLI_CORN, BROCCOLI_PUMPKIN, BROCCOLI_AVOCADO_FISH_A, AVOCADO_SALAD_CORN, AVOCADO_SALAD_PUMPKIN, CARROT_AVOCADO_FISH_B, BROCCOLI_AVOCADO_FISH_B]},
]


static func deck_for_seed(seed_value: int) -> Dictionary:
	var random := RandomNumberGenerator.new()
	random.seed = seed_value
	return DECKS[random.randi_range(0, DECKS.size() - 1)].duplicate(true)
