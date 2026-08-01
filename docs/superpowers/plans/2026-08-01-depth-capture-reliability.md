# Depth Capture Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make protocol-v4 depth images render real scene geometry, validate as genuine contract-compliant PNGs, avoid excess render resolution, and be clearly described to MCP players.

**Architecture:** Keep the existing synchronous observer and protocol-v4 DTO boundaries. Repair the Godot off-screen renderer so its camera shares the source `World3D`, render directly at the requested size, and lock the behavior with a graphical integration test. At the Python trust boundary, parse and validate the exact PNG structure and decompressed scanlines using only the standard library before projecting image bytes to MCP.

**Tech Stack:** Godot 4 GDScript and spatial shaders; Python 3 standard library (`struct`, `zlib`); pytest; MCP Python SDK.

## Global Constraints

- Keep protocol version 4 and the existing 8 MiB transport limit.
- Keep screenshot JPEG and depth PNG dimensions at 1024×576.
- Keep depth encoding `linear_depth_normalized_8bit`, near distance 0.05 metres, and far distance 4000.0 metres.
- Keep Godot observer APIs synchronous and preserve screenshot-only trajectory logging.
- Add no production Python dependency.
- Do not alter unrelated session/AWM or timeout-recovery behavior.

---

### Task 1: Lock and repair rendered depth capture

**Files:**
- Create: `tests/ai_play/test_ai_play_depth_capture_rendered.gd`
- Modify: `addons/cogito/AIPlay/ai_play_depth_map.gdshader:11-17`
- Modify: `addons/cogito/AIPlay/ai_play_depth_capture.gd:24-54,70-76`
- Test: `tests/ai_play/test_ai_play_depth_capture.gd`

**Interfaces:**
- Consumes: `AIPlayDepthCapture.capture(source_camera: Camera3D, width: int, height: int) -> Dictionary`
- Produces: a valid depth payload whose PNG contains nearer geometry darker than far background, and an internal capture viewport sized to the requested output.

- [x] **Step 1: Write the renderer-backed failing test**

Create a graphical `SceneTree` test that skips only when `DisplayServer.get_name() == "headless"`, adds a real `Node3D`, `Camera3D`, and centered `MeshInstance3D` cube to the root viewport, then calls `capture(camera, 96, 54)`. Decode the PNG and assert literal behaviors:

```gdscript
var center_depth: float = image.get_pixel(48, 27).r
var corner_depth: float = image.get_pixel(2, 2).r
_assert(center_depth < corner_depth, "foreground geometry is nearer than background")
_assert(corner_depth > 0.9, "background reaches the far depth value")
var depth_viewport: SubViewport = capture.get_node("AIPlayDepthViewport")
_assert(depth_viewport.size == Vector2i(96, 54), "capture renders at requested size")
```

The production mutation this catches is an invalid shader, `own_world_3d = true`, reversed near/far output, or rendering at the source viewport size.

- [x] **Step 2: Run the graphical test and verify RED**

Run:

```bash
godot --path . --script tests/ai_play/test_ai_play_depth_capture_rendered.gd
```

Expected: exit 1 because the current shader fails compilation and/or the returned image contains no foreground depth; the requested-size assertion also fails when the root viewport is not 96×54.

- [x] **Step 3: Apply the minimum rendering fixes**

In the shader, use valid entry-point declarations:

```glsl
void vertex() {
    POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

void fragment() {
    // Existing reverse-Z reconstruction and normalization remain unchanged.
}
```

In `capture()`, set `_depth_viewport.size` directly from the requested dimensions and remove the post-readback resize. In `_ensure_capture_viewport()`, share the source world:

```gdscript
_depth_viewport.size = Vector2i(maxi(2, width), maxi(2, height))
_depth_viewport.own_world_3d = false
_depth_viewport.world_3d = world
```

Keep the dedicated capture layer. Remove `RenderingServer.force_sync()` only if repeated graphical runs still read the current frame using `force_draw(false)` plus `get_image()`.

- [x] **Step 4: Verify GREEN and fallback compatibility**

Run each graphical command three times to catch stale readback, then run the fallback test:

```bash
godot --path . --script tests/ai_play/test_ai_play_depth_capture_rendered.gd
godot --path . --script tests/ai_play/test_ai_play_depth_capture_rendered.gd
godot --path . --script tests/ai_play/test_ai_play_depth_capture_rendered.gd
godot --headless --path . --script tests/ai_play/test_ai_play_depth_capture.gd
```

Expected: all exit 0 without shader errors; rendered output reports center depth below corner depth and fallback remains a decodable 1024×576 PNG.

---

### Task 2: Strictly validate depth PNGs and fixed depth metadata

**Files:**
- Modify: `ai_play/tests/test_observation_schema.py`
- Modify: `ai_play/src/ai_play/observation_schema.py`

**Interfaces:**
- Consumes: Base64 PNG bytes and depth metadata from the untrusted Godot observation DTO.
- Produces: `_validate_depth_png(data: bytes) -> None`, raising `ObservationValidationError` unless bytes are exactly a decodable 1024×576, 8-bit, non-interlaced RGB PNG with valid chunks and scanlines.

- [x] **Step 1: Replace the fake fixture with a real PNG builder**

In the test file, build literal RGB scanlines and valid chunks with `struct.pack` and `zlib.crc32`:

```python
def png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def depth_png(width=1024, height=576, idat_data=None) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    rows = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))
    compressed = zlib.compress(rows) if idat_data is None else idat_data
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", compressed)
        + png_chunk(b"IEND", b"")
    )
```

Make existing expected-byte assertions compare with the returned fixture rather than the old signature-only byte string.

- [x] **Step 2: Add malformed-input tests and verify RED**

Add tests that independently submit:

- a PNG with an invalid IHDR CRC;
- a valid 512×576 IHDR while DTO metadata says 1024×576;
- a CRC-valid IDAT containing invalid zlib bytes;
- a valid PNG followed by bytes ending in another fake IEND marker;
- `near_meters = 0.1`;
- `far_meters = 1000.0`.

Run:

```bash
PYTHONPATH=ai_play/src python3 -m pytest ai_play/tests/test_observation_schema.py -q
```

Expected: the new malformed PNG and alternative-range cases fail because the current validator checks only the signature, suffix, broad numeric ranges, and declared DTO dimensions.

- [x] **Step 3: Implement exact standard-library PNG validation**

Add protocol constants and a private validator. It must:

1. consume the signature;
2. bounds-check every chunk length before slicing;
3. validate every chunk CRC with `zlib.crc32`;
4. require first/unique IHDR with literal tuple `(1024, 576, 8, 2, 0, 0, 0)`;
5. collect one consecutive IDAT sequence;
6. require zero-length IEND at the exact end of input;
7. reject unsupported critical chunks;
8. decompress IDAT with `zlib.decompressobj()`, requiring `eof`, no unused/unconsumed data, and exactly `576 * (1 + 1024 * 3)` bytes;
9. require each scanline filter byte to be in `0..4`.

Call this validator after Base64 decoding, and require depth metadata to equal the fixed protocol constants rather than merely being ordered.

- [x] **Step 4: Verify GREEN**

Run:

```bash
PYTHONPATH=ai_play/src python3 -m pytest ai_play/tests/test_observation_schema.py -q
```

Expected: all schema tests pass, including the genuine PNG projection and every malformed rejection case.

---

### Task 3: Explain the two MCP image blocks

**Files:**
- Modify: `ai_play/tests/test_mcp_server.py`
- Modify: `tests/test_ai_play_codex_orchestrator.py`
- Modify: `ai_play/src/ai_play/mcp_server.py:170-172`
- Modify: `tools/ai_play_codex_orchestrator.py:149-167`

**Interfaces:**
- Consumes: MCP tool metadata and the generated isolated-player developer instructions.
- Produces: descriptions that identify image 1 as colour JPEG, image 2 as depth PNG, and dark/white depth semantics.

- [x] **Step 1: Add prompt and tool-description tests**

Extend the orchestrator instruction test with literal assertions for `第一张图片`, `第二张图片`, `JPEG`, `PNG`, `越暗表示越近`, and `白色`. Add an MCP client test that calls `list_tools()`, finds `observe`, and asserts the same image ordering and depth semantics in its description.

The production mutation this catches is reverting either public description to the old screenshot-only wording.

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src python3 -m pytest ai_play/tests/test_mcp_server.py tests/test_ai_play_codex_orchestrator.py -q
```

Expected: new description assertions fail against the current screenshot-only text.

- [x] **Step 3: Update public descriptions minimally**

Update the `observe` docstring and the isolated-player instructions. State that the first image is the normal JPEG screenshot, the second is the PNG depth image, darker pixels are nearer, and white represents the far limit or unavailable-depth fallback. Preserve the existing visual-only security restrictions.

- [x] **Step 4: Verify GREEN**

Re-run the Task 3 command and expect all tests to pass.

---

### Task 4: Full regression verification

**Files:**
- Verify only; modify production or tests only if a failure is caused by this plan's changes.

**Interfaces:**
- Consumes: all changes from Tasks 1–3.
- Produces: evidence that depth rendering, validation, MCP projection, logging, existing observers, session behavior, and source formatting remain correct.

- [x] **Step 1: Run all Python tests**

```bash
PYTHONPATH=ai_play/src python3 -m pytest ai_play/tests tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_supervisor.py tests/test_find_contract_awm_comparison.py -q
```

Expected: all tests pass with zero failures.

- [x] **Step 2: Run affected Godot headless tests**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_depth_capture.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/dailyroutine/test_home_ai_play_observer.gd
godot --headless --path . --script tests/garden/test_garden_ai_play.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: every script prints its pass marker and exits 0.

- [x] **Step 3: Run renderer and editor checks**

```bash
godot --path . --script tests/ai_play/test_ai_play_depth_capture_rendered.gd
godot --headless --path . --editor --quit
```

Expected: renderer test exits 0 without shader errors; editor exits 0 without parse failures.

- [ ] **Step 4: Inspect final diff and formatting**

```bash
git diff --check
git status --short
git diff --stat ec31baed..HEAD
```

Expected: no whitespace errors and only the files named by this plan are modified.
