shader_type spatial;

// A full-screen post-process quad rendered inside the depth-capture viewport.
render_mode unshaded, depth_draw_never, cull_disabled, fog_disabled;

uniform sampler2D depth_texture : source_color, hint_depth_texture, repeat_disable, filter_nearest;
uniform float near_meters = 0.05;
uniform float far_meters = 4000.0;


void vertex() {
	// Godot 4.3+ uses reversed Z, so the clip-space near plane is 1.0.
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}


void fragment() {
	float raw_depth = textureLod(depth_texture, SCREEN_UV, 0.0).r;
	vec3 ndc;
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	ndc = vec3(SCREEN_UV, raw_depth) * 2.0 - 1.0;
#else
	ndc = vec3(SCREEN_UV * 2.0 - 1.0, raw_depth);
#endif
	vec4 view = INV_PROJECTION_MATRIX * vec4(ndc, 1.0);
	view.xyz /= view.w;
	float linear_depth = max(-view.z, near_meters);
	float normalized_depth = clamp(
		(linear_depth - near_meters) / max(far_meters - near_meters, 0.000001),
		0.0,
		1.0
	);
	ALBEDO = vec3(normalized_depth);
}
