# Depth Capture Reliability Design

## Goal

Make protocol-v4 depth observations render real gameplay geometry, reject malformed depth payloads before they reach MCP clients, remain understandable to isolated players, and avoid unnecessary off-screen rendering cost.

## Scope

This change keeps the existing public contract:

- protocol version 4;
- a 1024×576 JPEG screenshot followed by a 1024×576 PNG depth image;
- `linear_depth_normalized_8bit` encoding;
- 0.05 metre near depth and 4000.0 metre far depth;
- synchronous Godot observer APIs;
- screenshot-only trajectory persistence.

It does not redesign the depth encoding, make observers asynchronous, or add a Python imaging dependency.

## Godot Rendering Design

`AIPlayDepthCapture` continues to use a dedicated `SubViewport`, camera, and full-screen spatial quad. The depth shader uses valid Godot shader entry points, reconstructs view-space distance from the viewport depth texture, and encodes the normalized value as RGB.

The capture viewport shares the source camera's `World3D`; it must not enable `own_world_3d`. A reserved render layer keeps the full-screen quad visible to the capture camera and hidden from the player's camera. Camera projection and transform properties remain synchronized before each capture.

The capture viewport renders directly at the requested 1024×576 output size rather than rendering at the source viewport resolution and resizing afterward. The synchronous observer contract remains intact. Explicit render synchronization is retained only where a renderer-backed regression test proves it is required for a current-frame readback.

If there is no valid camera, no world, a headless display, or a failed readback, the existing all-white PNG fallback remains the safe result.

## Python Boundary Validation

Depth image validation remains in `observation_schema.py` and uses only the Python standard library. Validation must reject a payload unless all of the following are true:

- Base64 is valid and the decoded payload is within the existing byte limit;
- the PNG signature is correct;
- chunks are structurally complete, ordered, and CRC-valid;
- IHDR declares exactly 1024×576, 8-bit RGB, standard compression/filter methods, and no interlacing;
- at least one IDAT chunk exists and the concatenated stream decompresses successfully;
- decompressed scanlines have the exact expected size and legal PNG filter bytes;
- IEND is valid and no trailing bytes remain;
- MIME type, metadata dimensions, encoding, `near_meters`, and `far_meters` exactly match the protocol-v4 constants.

The validator returns a fresh safe DTO as it does today. Invalid images fail before construction of MCP `ImageContent`.

## MCP Presentation

The `observe` tool description and isolated-player instructions state that image block 1 is the JPEG colour screenshot and image block 2 is the PNG depth image. They also explain that darker depth pixels are nearer and white pixels represent the far limit or fallback background. No Base64 or filesystem access is exposed to the player.

## Testing

Testing is split by responsibility:

1. The existing headless Godot test continues to verify fallback PNG metadata and decoding.
2. A renderer-backed Godot test builds a small scene with a real camera and geometry at known distances. It fails on shader compilation, an isolated World3D, a uniform result, or reversed near/far ordering.
3. Python schema tests use a genuinely valid 1024×576 RGB PNG fixture and add malformed cases for invalid CRC, mismatched IHDR dimensions, corrupt compressed data, trailing bytes, and non-contract near/far values.
4. MCP tests continue to verify JPEG-then-PNG ordering, Base64-free structured content, and screenshot-only trajectory persistence.

Final verification runs the full Python suite, affected Godot headless tests, the renderer-backed test, an editor parse/import check, and `git diff --check`.

## Failure and Compatibility Behavior

Rendering failures never publish arbitrary GPU bytes: they use the existing white fallback. Protocol-invalid Python payloads raise `ObservationValidationError` and are not forwarded to the model. Existing protocol-v4 clients retain the same fields, dimensions, ordering, and encoding metadata, so no migration is required.
