#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    print(f"Patched {path.relative_to(ROOT)}")


model_path = ROOT / "cont/base/springcontent/shaders/GLSL/ModelFragProgGL4.glsl"
model_old = '''vec3 GetShadowMult(vec3 shadowCoord, float NdotL) {
	#if (USE_SHADOWS == 1)
		float sh = min(texture(shadowTex, shadowCoord).r, smoothstep(0.0, 0.35, NdotL));
		vec3 shColor = texture(shadowColorTex, shadowCoord.xy).rgb;
		return mix(1.0, sh, shadowDensity.y) * shColor;
	#else
		return vec3(1.0);
	#endif
}
'''
model_new = '''float TEK2SoftShadow(vec3 shadowCoord) {
	const vec2 disk[8] = vec2[8](
		vec2(-0.613392,  0.617481), vec2( 0.170019, -0.040254),
		vec2(-0.299417,  0.791925), vec2( 0.645680,  0.493210),
		vec2(-0.651784, -0.717887), vec2( 0.421003,  0.027070),
		vec2(-0.817194, -0.271096), vec2(-0.705374, -0.668203)
	);

	vec2 texel = 1.0 / vec2(textureSize(shadowTex, 0));
	float receiverDepth = clamp(shadowCoord.z, 0.0, 1.0);
	float radiusTexels = mix(0.85, 3.25, smoothstep(0.18, 0.92, receiverDepth));
	float angle = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453) * 6.2831853;
	mat2 rotation = mat2(cos(angle), -sin(angle), sin(angle), cos(angle));

	float visibility = 0.0;
	for (int i = 0; i < 8; ++i)
		visibility += texture(shadowTex, vec3(shadowCoord.xy + rotation * disk[i] * texel * radiusTexels, shadowCoord.z)).r;

	return visibility * 0.125;
}

vec3 GetShadowMult(vec3 shadowCoord, float NdotL) {
	#if (USE_SHADOWS == 1)
		float sh = min(TEK2SoftShadow(shadowCoord), smoothstep(0.0, 0.35, NdotL));
		vec3 shColor = texture(shadowColorTex, shadowCoord.xy).rgb;
		return mix(1.0, sh, shadowDensity.y) * shColor;
	#else
		return vec3(1.0);
	#endif
}
'''
replace_once(model_path, model_old, model_new)

smf_path = ROOT / "cont/base/springcontent/shaders/GLSL/SMFFragProg.glsl"
smf_anchor = '''#ifdef SMF_ADV_SHADING
	vec3 GetFragmentNormal(vec2 uv) {
'''
smf_insert = '''#ifdef HAVE_SHADOWS
float TEK2SoftGroundShadow(vec4 shadowPos) {
	const vec2 disk[8] = vec2[8](
		vec2(-0.613392,  0.617481), vec2( 0.170019, -0.040254),
		vec2(-0.299417,  0.791925), vec2( 0.645680,  0.493210),
		vec2(-0.651784, -0.717887), vec2( 0.421003,  0.027070),
		vec2(-0.817194, -0.271096), vec2(-0.705374, -0.668203)
	);

	vec3 coord = shadowPos.xyz / shadowPos.w;
	vec2 texel = 1.0 / vec2(textureSize(shadowTex, 0));
	float receiverDepth = clamp(coord.z, 0.0, 1.0);
	float radiusTexels = mix(0.85, 3.25, smoothstep(0.18, 0.92, receiverDepth));
	float angle = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453) * 6.2831853;
	mat2 rotation = mat2(cos(angle), -sin(angle), sin(angle), cos(angle));

	float visibility = 0.0;
	for (int i = 0; i < 8; ++i)
		visibility += shadow2D(shadowTex, vec3(coord.xy + rotation * disk[i] * texel * radiusTexels, coord.z)).r;

	return visibility * 0.125;
}
#endif

#ifdef SMF_ADV_SHADING
	vec3 GetFragmentNormal(vec2 uv) {
'''
replace_once(smf_path, smf_anchor, smf_insert)

smf_sample_old = '''		shadowCoeff = mix(vec3(1.0), shadow2DProj(shadowTex, vertexShadowPos).r * shadowColor, groundShadowDensity);
'''
smf_sample_new = '''		shadowCoeff = mix(vec3(1.0), TEK2SoftGroundShadow(vertexShadowPos) * shadowColor, groundShadowDensity);
'''
replace_once(smf_path, smf_sample_old, smf_sample_new)

print("TEK2 soft-shadow patch applied successfully.")
