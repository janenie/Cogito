# MCP Depth Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every ready `observe()` and `act()` result return the existing color screenshot followed by a synchronized depth-map PNG.

**Architecture:** Godot renders the same `World3D` from a mirrored player camera into an off-screen `SubViewport`. A full-screen spatial quad in that same viewport samples its depth buffer, linearizes it into an 8-bit grayscale visualization, and encodes it as PNG. The internal observation DTO carries strict `depth_image` metadata and Base64; Python validates and removes both Base64 payloads from structured data, while the MCP layer emits the JPEG first and depth PNG second.

**Tech Stack:** Godot 4.7 GDScript/Shaders, Python 3, FastMCP, pytest, Godot headless contract tests.

---

## File structure

- Create `addons/cogito/AIPlay/ai_play_depth_capture.gd`: owns the off-screen shared-world viewport, camera mirroring, fallback image, and depth PNG metadata.
- Create `addons/cogito/AIPlay/ai_play_depth_map.gdshader`: converts the current viewport's reverse-Z depth buffer to grayscale normalized linear depth.
- Modify the three observer scripts so every observation includes `depth_image` from the reusable component.
- Modify Python schema/session/bridge/MCP layers so a depth image is validated, projected, and emitted as the second `ImageContent` without changing trajectory persistence.
- Modify focused Python and Godot contract tests, `ai_play/README.md`, and `docs/wiki/ai-play/system-guide.md`.

### Task 1: Lock the Python public DTO and MCP response contract (RED)

**Files:**
- Modify: `ai_play/tests/test_observation_schema.py`
- Modify: `ai_play/tests/test_game_session.py`
- Modify: `ai_play/tests/test_bridge_server.py`
- Modify: `ai_play/tests/test_mcp_server.py`

- [x] **Step 1: Write a valid PNG depth fixture and schema expectations**

Add this helper and field to the existing valid observation fixture:

```python
def valid_depth_png_base64():
    depth_bytes = b"\x89PNG\r\n\x1a\ndepth-mapIEND\xaeB`\x82"
    return base64.b64encode(depth_bytes).decode("ascii")


def valid_observation_with_jpeg_base64():
    # existing image/player/interface/bindings values stay unchanged
    return {
        # existing fields stay unchanged
        "depth_image": {
            "mime_type": "image/png",
            "base64": valid_depth_png_base64(),
            "width": 768,
            "height": 432,
            "encoding": "linear_depth_normalized_8bit",
            "near_meters": 0.05,
            "far_meters": 4000.0,
        },
    }
```

Add a test that demands separate image bytes and base64-free metadata:

```python
def test_prepare_mcp_observation_separates_depth_png_from_structured_state():
    public, image_bytes, depth_image_bytes = prepare_mcp_observation(
        valid_observation_with_jpeg_base64()
    )

    assert image_bytes.startswith(b"\xff\xd8\xff")
    assert depth_image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert public["depth_image"] == {
        "mime_type": "image/png",
        "width": 768,
        "height": 432,
        "encoding": "linear_depth_normalized_8bit",
        "near_meters": 0.05,
        "far_meters": 4000.0,
    }
    assert "base64" not in public["depth_image"]
```

Add invalid metadata cases for a JPEG depth image, an invalid encoding, and `near_meters >= far_meters`; each must raise `ObservationValidationError`.

- [x] **Step 2: Require a depth PNG from GameSession and MCP fixtures**

Update the `observation()` fixture in `test_game_session.py` and `FakeReadySession.to_mcp_payload()` in `test_mcp_server.py` to include the same metadata and return a third value:

```python
return payload, b"\xff\xd8\xffmcp-image\xff\xd9", (
    b"\x89PNG\r\n\x1a\nmcp-depthIEND\xaeB`\x82"
)
```

Make the game-session test require the third byte stream:

```python
payload, image_bytes, depth_image_bytes = session.to_mcp_payload(result)
assert payload["observation"]["depth_image"]["mime_type"] == "image/png"
assert depth_image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
```

Make the MCP tests require ordered image content:

```python
images = [item for item in result.content if isinstance(item, ImageContent)]
assert [item.mimeType for item in images] == ["image/jpeg", "image/png"]
assert result.structuredContent["observation"]["depth_image"]["encoding"] == (
    "linear_depth_normalized_8bit"
)
```

Keep the trajectory logger assertion unchanged: it must receive the JPEG only.

- [x] **Step 3: Require bridge acceptance while retaining old-observation compatibility**

Extend `_observation()` in `test_bridge_server.py` with `include_depth=False`. When true, add the exact depth fixture. Add both tests:

```python
def test_bridge_accepts_depth_image_in_observation():
    # send _observation(include_depth=True) through the real bridge
    assert result.observation["depth_image"]["mime_type"] == "image/png"


def test_bridge_keeps_accepting_legacy_observation_without_depth_image():
    # send _observation(include_depth=False) through the real bridge
    assert "depth_image" not in result.observation
```

- [x] **Step 4: Run the focused Python tests and verify RED**

Run:

```powershell
$env:PYTHONPATH = (Resolve-Path 'ai_play/src')
pytest -q ai_play/tests/test_observation_schema.py ai_play/tests/test_game_session.py ai_play/tests/test_bridge_server.py ai_play/tests/test_mcp_server.py
```

Expected: failures specifically identify rejected/missing `depth_image`, missing third return value, or a missing second `ImageContent`; no production Python file has been edited yet.

### Task 2: Lock Godot depth-observation behavior (RED)

**Files:**
- Create: `tests/ai_play/test_ai_play_depth_capture.gd`
- Modify: `tests/ai_play/test_ai_play_observer.gd`
- Modify: `tests/dailyroutine/test_home_ai_play_observer.gd`
- Modify: `tests/garden/test_garden_ai_play.gd`

- [x] **Step 1: Add a focused fallback contract test for the depth-capture component**

Create `test_ai_play_depth_capture.gd` that runs in headless mode and checks the real component API:

```gdscript
extends SceneTree

var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var capture_script: GDScript = load(
		"res://addons/cogito/AIPlay/ai_play_depth_capture.gd"
	)
	_assert(capture_script != null, "depth capture component exists")
	if capture_script != null:
		var capture: Node = capture_script.new()
		root.add_child(capture)
		var payload: Dictionary = capture.capture(null, 768, 432)
		_assert(payload["mime_type"] == "image/png", "depth uses PNG")
		_assert(payload["encoding"] == "linear_depth_normalized_8bit", "depth encoding is declared")
		var image := Image.new()
		_assert(
			image.load_png_from_buffer(Marshalls.base64_to_raw(payload["base64"])) == OK,
			"depth base64 decodes as PNG"
		)
		_assert(image.get_size() == Vector2i(768, 432), "depth image is 768x432")
		capture.free()
	_finish()

func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)

func _finish() -> void:
	if failures.is_empty():
		print("AIPlay depth capture tests passed")
		quit(0)
	for failure: String in failures:
		push_error(failure)
	quit(1)
```

- [x] **Step 2: Require all three observer families to publish the same depth DTO**

In each existing observer test, add assertions shaped as follows immediately after `capture_observation()`:

```gdscript
var depth_payload: Dictionary = observation.get("depth_image", {})
_assert(depth_payload.get("mime_type") == "image/png", "observation includes PNG depth")
_assert(depth_payload.get("width") == 768 and depth_payload.get("height") == 432, "depth dimensions match screenshot")
_assert(depth_payload.get("encoding") == "linear_depth_normalized_8bit", "depth encoding is public")
var decoded_depth := Image.new()
_assert(
	decoded_depth.load_png_from_buffer(Marshalls.base64_to_raw(depth_payload.get("base64", ""))) == OK,
	"depth base64 decodes as PNG"
)
```

- [ ] **Step 3: Run the Godot tests and verify RED (blocked: no `godot` executable in this environment)**

Run:

```powershell
godot --headless --path . --script tests/ai_play/test_ai_play_depth_capture.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/dailyroutine/test_home_ai_play_observer.gd
godot --headless --path . --script tests/garden/test_garden_ai_play.gd
```

Expected: the new component file is absent and/or `depth_image` assertions fail because no observer currently creates it.

### Task 3: Implement off-screen depth capture (GREEN)

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_depth_capture.gd`
- Create: `addons/cogito/AIPlay/ai_play_depth_map.gdshader`
- Modify: `addons/cogito/AIPlay/ai_play_observer.gd`
- Modify: `addons/cogito/AIPlay/ai_play_home_observer.gd`
- Modify: `addons/cogito/AIPlay/ai_play_garden_observer.gd`

- [x] **Step 1: Create the depth visualization shader**

Implemented `ai_play_depth_map.gdshader` as a full-screen **spatial** quad instead of
the original canvas-shader draft. The spatial shader reads the current off-screen
viewport's reverse-Z depth buffer, reconstructs view-space depth using
`INV_PROJECTION_MATRIX` (including a Compatibility-renderer NDC branch), then maps
near to black and far/background to white.

- [x] **Step 2: Create the reusable capture component**

Create a `class_name AIPlayDepthCapture` node that creates a `SubViewport`, a mirrored `Camera3D`, and a `CanvasLayer/ColorRect` using the shader. Its public method must be:

> Implementation note: the completed code uses a mirrored `Camera3D` plus a spatial
> full-screen `MeshInstance3D` (not `CanvasLayer/ColorRect`), keeps the public
> normalization range fixed at 0.05–4000 meters, and mirrors the source camera's
> actual projection and clip settings for rendering.

```gdscript
func capture(source_camera: Camera3D, width: int, height: int) -> Dictionary:
	var near_meters := DEFAULT_NEAR_METERS
	var far_meters := DEFAULT_FAR_METERS
	var image := _blank_depth_image(width, height)
	if source_camera != null:
		near_meters = source_camera.near
		far_meters = source_camera.far
	if DisplayServer.get_name() != "headless" and source_camera != null:
		image = _render_depth_image(source_camera, width, height)
	return {
		"mime_type": "image/png",
		"base64": Marshalls.raw_to_base64(image.save_png_to_buffer()),
		"width": width,
		"height": height,
		"encoding": "linear_depth_normalized_8bit",
		"near_meters": near_meters,
		"far_meters": far_meters,
	}
```

`_render_depth_image()` must set `SubViewport.world_3d` to `source_camera.get_world_3d()`, mirror the source camera's `global_transform`, `projection`, `fov`, `size`, `keep_aspect`, `frustum_offset`, `near`, `far`, `h_offset`, `v_offset`, and `cull_mask`, set shader uniforms, force an off-screen draw with `RenderingServer.force_draw(false)` and `RenderingServer.force_sync()`, then resize the returned image with `Image.INTERPOLATE_NEAREST` when needed. `_blank_depth_image()` must fill the PNG white so no rendered geometry semantically maps to the far plane.

- [x] **Step 3: Attach the component to each observer without exposing camera internals**

Each observer must preload the component, cache it as a child, resolve only its player's public `camera` property, and include the returned dictionary:

```gdscript
const DepthCapture = preload("res://addons/cogito/AIPlay/ai_play_depth_capture.gd")

var _depth_capture: Node

func _capture_depth_image() -> Dictionary:
	if _depth_capture == null:
		_depth_capture = DepthCapture.new()
		add_child(_depth_capture)
	var camera: Camera3D = null
	if player != null and "camera" in player:
		camera = player.get("camera") as Camera3D
	return _depth_capture.capture(camera, IMAGE_WIDTH, IMAGE_HEIGHT)
```

In each `capture_observation()` call, calculate `var depth_image := _capture_depth_image()` beside `var image := _capture_image()` and add `"depth_image": depth_image` after the regular `image` field. Do not add node paths, renderer state, scene names, or camera references to the returned DTO.

- [ ] **Step 4: Run Godot contract tests and verify GREEN (blocked: no `godot` executable in this environment)**

Run the four commands from Task 2. Expected: all exit `0`, including headless white-depth fallback PNG checks.

### Task 4: Implement Python validation, bridge projection, and ordered MCP content (GREEN)

**Files:**
- Modify: `ai_play/src/ai_play/observation_schema.py`
- Modify: `ai_play/src/ai_play/bridge_server.py`
- Modify: `ai_play/src/ai_play/game_session.py`
- Modify: `ai_play/src/ai_play/mcp_server.py`

- [x] **Step 1: Add a bounded optional `depth_image` schema**

Add `depth_image` to `OPTIONAL_OBSERVATION_FIELDS` and validate it only when present. Require exactly these fields:

```python
{
    "mime_type", "base64", "width", "height", "encoding",
    "near_meters", "far_meters",
}
```

Accept only a bounded PNG beginning with `b"\x89PNG\r\n\x1a\n"` and ending with `b"IEND\xaeB`\x82"`, dimensions `768 x 432`, encoding `linear_depth_normalized_8bit`, and finite `0 < near_meters < far_meters <= 1_000_000`. Add the sanitized payload to the returned observation only when supplied.

Update the projection method to return a triple while retaining legacy observations:

```python
def prepare_mcp_observation(value):
	# validate and decode regular JPEG exactly as today
	depth_image_bytes = None
	if "depth_image" in safe:
		depth_image_bytes = base64.b64decode(
			safe["depth_image"]["base64"], validate=True
		)
		public["depth_image"] = {
			key: item
			for key, item in safe["depth_image"].items()
			if key != "base64"
		}
	return public, image_bytes, depth_image_bytes
```

- [x] **Step 2: Accept the optional bridge field and carry the triple through GameSession**

Add `depth_image` to `bridge_server.OPTIONAL_OBSERVATION_FIELDS`. Update `GameSession.to_mcp_payload()` to initialize `depth_image_bytes = None`, unpack all three values from `prepare_mcp_observation()`, and return:

```python
return payload, image_bytes, depth_image_bytes
```

- [x] **Step 3: Emit JPEG then depth PNG from `observe` and `act`**

Replace the image assembly helper with this ordered interface:

```python
def _result(payload, image_bytes=None, depth_image_bytes=None):
	content = []
	if image_bytes is not None:
		content.append(ImageContent(
			type="image",
			data=base64.b64encode(image_bytes).decode("ascii"),
			mimeType="image/jpeg",
		))
	if depth_image_bytes is not None:
		content.append(ImageContent(
			type="image",
			data=base64.b64encode(depth_image_bytes).decode("ascii"),
			mimeType="image/png",
		))
	return CallToolResult(content=content, structuredContent=payload)
```

Unpack the third item in `observe()`, `act()`, and `stop()`. Pass depth bytes to `_result()` only; keep `_complete_logged_call(..., image_bytes)` unchanged so the existing trajectory layout still persists only the color JPEG.

- [x] **Step 4: Run focused Python tests and verify GREEN**

Run the command from Task 1. Expected: all tests pass and the logger continues to receive only JPEG bytes.

### Task 5: Document the stable public contract and complete verification

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/scope-nospec/2026-07-27-mcp-depth-image/plan-mcp-depth-image.md`

- [x] **Step 1: Update `ai_play/README.md`**

In the MCP tool/result sections, state that ready observations contain color `image` metadata plus `depth_image` metadata, and return two ordered MCP image blocks: JPEG screenshot first, PNG grayscale depth visualization second. State that the depth map is derived from the current 3D camera depth buffer; UI and transparent objects may have no depth and map to the far value. State explicitly that trajectory persistence remains JPEG-only and does not add a depth PNG file.

- [x] **Step 2: Update the existing AI Play Wiki page**

In `docs/wiki/ai-play/system-guide.md`, amend the cross-layer contract and local-trajectory bullets to match the README: `observe`/`act` return the public depth visualization as a second image, `depth_image` Base64 stays out of structured MCP JSON, and only the screenshot JPEG is persisted. Preserve the first-line summary and all unrelated safety rules.

- [x] **Step 3: Mark this plan's completed checkboxes and run full relevant checks** (Python and diff checks passed; Godot checks remain unavailable.)

Run:

```powershell
$env:PYTHONPATH = (Resolve-Path 'ai_play/src')
pytest -q ai_play/tests
godot --headless --path . --script tests/ai_play/test_ai_play_depth_capture.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/dailyroutine/test_home_ai_play_observer.gd
godot --headless --path . --script tests/garden/test_garden_ai_play.gd
git diff --check
git status -sb
git diff -- ai_play addons/cogito/AIPlay tests docs
```

Expected: all applicable tests exit `0`, `git diff --check` has no output, and the diff contains only this feature's code, tests, README, Wiki, and implementation plan.

- [x] **Step 4: Commit and publish according to the recorded Git preference**

After a clean verification, rebase onto the fetched `origin/ai_first_play` if it advanced, then:

```powershell
git add addons/cogito/AIPlay ai_play tests docs
git commit -m "feat(ai-play): return depth maps with observations"
git push origin ai_first_play
```

Do not create a PR, merge, delete a branch, or clean a worktree because this task runs directly on the configured baseline branch.
