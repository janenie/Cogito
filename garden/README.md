# Garden

Garden is a first-person neighborhood gardening task integrated into this
COGITO repository.

## Run

From the repository root:

```bash
godot --path . garden/scenes/garden_vertical_slice.tscn \
  -- --ai-play-scenario=garden_watering
```

To explicitly enable the local AI Play bridge:

```bash
godot --path . garden/scenes/garden_vertical_slice.tscn \
  -- --ai-play --ai-play-scenario=garden_watering
```

The player uses four full watering cans to water two lawns at the sunflower
house and two at the hydrangea house. While the HUD shows rain, the player must
press the orchid house doorbell before the rain ends. AI Play remains disabled
unless the exact `--ai-play` user argument is present.

## Garden orders neighborhood

The garden-order prototype uses a separate third-person inspection scene with
ten numbered homes around a central tool plaza. It deliberately contains no
order schedule or AI solution data.

```bash
godot --path . garden/scenes/garden_orders_neighborhood.tscn
```
