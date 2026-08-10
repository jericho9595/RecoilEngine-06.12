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


# ---------------------------------------------------------------------------
# 1) ShadowHandler: expose the same depth texture through a raw-depth sampler
#    object. The normal compare sampler stays untouched for engine/Lua compat.
# ---------------------------------------------------------------------------

shadow_h = ROOT / "rts/Rendering/ShadowHandler.h"

replace_once(
    shadow_h,
    '''\tvoid SetupShadowTexSampler(unsigned int texUnit, bool enable = false) const;\n\tvoid SetupShadowTexSamplerRaw() const;\n\tvoid ResetShadowTexSampler(unsigned int texUnit, bool disable = false) const;\n\tvoid ResetShadowTexSamplerRaw() const;\n''',
    '''\tvoid SetupShadowTexSampler(unsigned int texUnit, bool enable = false) const;\n\tvoid SetupShadowTexSamplerRaw() const;\n\tvoid ResetShadowTexSampler(unsigned int texUnit, bool disable = false) const;\n\tvoid ResetShadowTexSamplerRaw() const;\n\n\t// TEK2 PCSS: bind the existing shadow depth texture with a sampler object\n\t// that disables hardware depth comparison, allowing blocker-depth reads.\n\tvoid SetupShadowDepthRawSampler(unsigned int texUnit, bool enable = false) const;\n\tvoid ResetShadowDepthRawSampler(unsigned int texUnit, bool disable = false) const;\n'''
)

replace_once(
    shadow_h,
    '''\tuint32_t shadowDepthTexture;\n\tuint32_t shadowColorTexture;\n''',
    '''\tuint32_t shadowDepthTexture;\n\tuint32_t shadowColorTexture;\n\tuint32_t shadowDepthRawSampler = 0;\n'''
)

shadow_cpp = ROOT / "rts/Rendering/ShadowHandler.cpp"

replace_once(
    shadow_cpp,
    '''\tglDeleteTextures(1, &shadowDepthTexture); shadowDepthTexture = 0;\n\tglDeleteTextures(1, &shadowColorTexture); shadowColorTexture = 0;\n''',
    '''\tglDeleteTextures(1, &shadowDepthTexture); shadowDepthTexture = 0;\n\tglDeleteTextures(1, &shadowColorTexture); shadowColorTexture = 0;\n\tif (shadowDepthRawSampler != 0) {\n\t\tglDeleteSamplers(1, &shadowDepthRawSampler);\n\t\tshadowDepthRawSampler = 0;\n\t}\n'''
)

replace_once(
    shadow_cpp,
    '''\tsmOpaqFBO.Unbind();\n\n\t// revert to FBO = 0 default\n\tglColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n\n\treturn status;\n}\n''',
    '''\tsmOpaqFBO.Unbind();\n\n\t// TEK2 PCSS: sampler objects let the same depth texture be bound twice:\n\t// one unit keeps the engine's sampler2DShadow compare state, while a second\n\t// unit exposes raw depth values to the blocker search. No shadow-map copy.\n\tif (status && globalRendering->haveGL4) {\n\t\tif (shadowDepthRawSampler != 0)\n\t\t\tglDeleteSamplers(1, &shadowDepthRawSampler);\n\n\t\tglGenSamplers(1, &shadowDepthRawSampler);\n\t\tglSamplerParameterfv(shadowDepthRawSampler, GL_TEXTURE_BORDER_COLOR, one);\n\t\tglSamplerParameteri(shadowDepthRawSampler, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER);\n\t\tglSamplerParameteri(shadowDepthRawSampler, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER);\n\t\tglSamplerParameteri(shadowDepthRawSampler, GL_TEXTURE_MIN_FILTER, GL_NEAREST);\n\t\tglSamplerParameteri(shadowDepthRawSampler, GL_TEXTURE_MAG_FILTER, GL_NEAREST);\n\t\tglSamplerParameteri(shadowDepthRawSampler, GL_TEXTURE_COMPARE_MODE, GL_NONE);\n\t}\n\n\t// revert to FBO = 0 default\n\tglColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);\n\n\treturn status;\n}\n'''
)

replace_once(
    shadow_cpp,
    '''void CShadowHandler::ResetShadowTexSamplerRaw() const\n{\n\tglTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_MODE, GL_NONE);\n\tglTexParameteri(GL_TEXTURE_2D, GL_DEPTH_TEXTURE_MODE, GL_LUMINANCE);\n}\n\n\nvoid CShadowHandler::CreateShadows()\n''',
    '''void CShadowHandler::ResetShadowTexSamplerRaw() const\n{\n\tglTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_MODE, GL_NONE);\n\tglTexParameteri(GL_TEXTURE_2D, GL_DEPTH_TEXTURE_MODE, GL_LUMINANCE);\n}\n\nvoid CShadowHandler::SetupShadowDepthRawSampler(unsigned int texUnit, bool enable) const\n{\n\tif (shadowDepthRawSampler == 0)\n\t\treturn;\n\n\tglActiveTexture(texUnit);\n\tglBindTexture(GL_TEXTURE_2D, shadowDepthTexture);\n\tglBindSampler(texUnit - GL_TEXTURE0, shadowDepthRawSampler);\n\n\tif (enable)\n\t\tglEnable(GL_TEXTURE_2D);\n}\n\nvoid CShadowHandler::ResetShadowDepthRawSampler(unsigned int texUnit, bool disable) const\n{\n\tif (shadowDepthRawSampler == 0)\n\t\treturn;\n\n\tglActiveTexture(texUnit);\n\tglBindSampler(texUnit - GL_TEXTURE0, 0);\n\tglBindTexture(GL_TEXTURE_2D, 0);\n\n\tif (disable)\n\t\tglDisable(GL_TEXTURE_2D);\n}\n\n\nvoid CShadowHandler::CreateShadows()\n'''
)

# ---------------------------------------------------------------------------
# 2) Bind raw depth for model GL4 (unit 6) and advanced SMF terrain (unit 3).
# ---------------------------------------------------------------------------

model_helpers = ROOT / "rts/Rendering/Common/ModelDrawerHelpers.cpp"

replace_once(
    model_helpers,
    '''\tif (shadowHandler.ShadowsLoaded()) {\n\t\tshadowHandler.SetupShadowTexSampler(GL_TEXTURE2, true);\n\t\tglActiveTexture(GL_TEXTURE3); glBindTexture(GL_TEXTURE_2D, shadowHandler.GetColorTextureID());\n\t}\n''',
    '''\tif (shadowHandler.ShadowsLoaded()) {\n\t\tshadowHandler.SetupShadowTexSampler(GL_TEXTURE2, true);\n\t\tglActiveTexture(GL_TEXTURE3); glBindTexture(GL_TEXTURE_2D, shadowHandler.GetColorTextureID());\n\t\tshadowHandler.SetupShadowDepthRawSampler(GL_TEXTURE6, true);\n\t}\n'''
)

replace_once(
    model_helpers,
    '''\tif (shadowHandler.ShadowsLoaded())\n\t\tshadowHandler.ResetShadowTexSampler(GL_TEXTURE2, true);\n\n\tglActiveTexture(GL_TEXTURE3);\n''',
    '''\tif (shadowHandler.ShadowsLoaded()) {\n\t\tshadowHandler.ResetShadowTexSampler(GL_TEXTURE2, true);\n\t\tshadowHandler.ResetShadowDepthRawSampler(GL_TEXTURE6, true);\n\t}\n\n\tglActiveTexture(GL_TEXTURE3);\n'''
)

smf_state = ROOT / "rts/Map/SMF/SMFRenderState.cpp"

replace_once(
    smf_state,
    '''\t\t\tif (isAdv) {\n\t\t\t\tglslShaders[n]->SetUniform("shadowTex", 4);\n''',
    '''\t\t\tif (isAdv) {\n\t\t\t\tglslShaders[n]->SetUniform("shadowDepthTex", 3);\n\t\t\t\tglslShaders[n]->SetUniform("shadowTex", 4);\n'''
)

replace_once(
    smf_state,
    '''\tif (isAdv && shadowHandler.ShadowsLoaded()) {\n\t\tshadowHandler.SetupShadowTexSampler(GL_TEXTURE4, true);\n\t\tglActiveTexture(GL_TEXTURE19); glBindTexture(GL_TEXTURE_2D, shadowHandler.GetColorTextureID());\n\t}\n''',
    '''\tif (isAdv && shadowHandler.ShadowsLoaded()) {\n\t\tshadowHandler.SetupShadowDepthRawSampler(GL_TEXTURE3, true);\n\t\tshadowHandler.SetupShadowTexSampler(GL_TEXTURE4, true);\n\t\tglActiveTexture(GL_TEXTURE19); glBindTexture(GL_TEXTURE_2D, shadowHandler.GetColorTextureID());\n\t}\n'''
)

replace_once(
    smf_state,
    '''\tif (isAdv && shadowHandler.ShadowsLoaded()) {\n\t\tshadowHandler.ResetShadowTexSampler(GL_TEXTURE4, true);\n\t\tglActiveTexture(GL_TEXTURE19); glBindTexture(GL_TEXTURE_2D, 0);\n\t}\n''',
    '''\tif (isAdv && shadowHandler.ShadowsLoaded()) {\n\t\tshadowHandler.ResetShadowDepthRawSampler(GL_TEXTURE3, true);\n\t\tshadowHandler.ResetShadowTexSampler(GL_TEXTURE4, true);\n\t\tglActiveTexture(GL_TEXTURE19); glBindTexture(GL_TEXTURE_2D, 0);\n\t}\n'''
)

# ---------------------------------------------------------------------------
# 3) Real PCSS for GL4 models.
#    - blocker search uses raw depth
#    - penumbra radius derives from receiver/blocker separation
#    - final filtering still uses the engine's hardware comparison sampler
# ---------------------------------------------------------------------------

model_frag = ROOT / "cont/base/springcontent/shaders/GLSL/ModelFragProgGL4.glsl"

replace_once(
    model_frag,
    '''#if (USE_SHADOWS == 1)\n\tlayout(binding = 2) uniform sampler2DShadow shadowTex;\n\tlayout(binding = 3) uniform sampler2D shadowColorTex;\n#endif\n''',
    '''#if (USE_SHADOWS == 1)\n\tlayout(binding = 2) uniform sampler2DShadow shadowTex;\n\tlayout(binding = 3) uniform sampler2D shadowColorTex;\n\tlayout(binding = 6) uniform sampler2D shadowDepthTex;\n#endif\n'''
)

replace_once(
    model_frag,
    '''vec3 GetShadowMult(vec3 shadowCoord, float NdotL) {\n\t#if (USE_SHADOWS == 1)\n\t\tfloat sh = min(texture(shadowTex, shadowCoord).r, smoothstep(0.0, 0.35, NdotL));\n\t\tvec3 shColor = texture(shadowColorTex, shadowCoord.xy).rgb;\n\t\treturn mix(1.0, sh, shadowDensity.y) * shColor;\n\t#else\n\t\treturn vec3(1.0);\n\t#endif\n}\n''',
    '''#if (USE_SHADOWS == 1)\nconst vec2 TEK2_PCSS_DISK[12] = vec2[12](\n\tvec2(-0.326212, -0.405810), vec2(-0.840144, -0.073580),\n\tvec2(-0.695914,  0.457137), vec2(-0.203345,  0.620716),\n\tvec2( 0.962340, -0.194983), vec2( 0.473434, -0.480026),\n\tvec2( 0.519456,  0.767022), vec2( 0.185461, -0.893124),\n\tvec2( 0.507431,  0.064425), vec2( 0.896420,  0.412458),\n\tvec2(-0.321940, -0.932615), vec2(-0.791559, -0.597705)\n);\n\nmat2 TEK2PCSSRotation(vec2 shadowUV, vec2 shadowSize) {\n\tvec2 cell = floor(shadowUV * shadowSize);\n\tfloat angle = fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453) * 6.28318530718;\n\tfloat s = sin(angle);\n\tfloat c = cos(angle);\n\treturn mat2(c, -s, s, c);\n}\n\nfloat TEK2PCSSShadow(vec3 shadowCoord, float NdotL) {\n\tvec2 shadowSize = vec2(textureSize(shadowDepthTex, 0));\n\tvec2 texel = 1.0 / shadowSize;\n\tmat2 rotation = TEK2PCSSRotation(shadowCoord.xy, shadowSize);\n\n\tfloat receiverDepth = clamp(shadowCoord.z, 0.0, 1.0);\n\tfloat depthBias = mix(0.00055, 0.00010, clamp(NdotL, 0.0, 1.0));\n\n\t// PCSS blocker search. For a directional area light the search region grows\n\t// with receiver depth in light space.\n\tfloat searchRadiusTexels = mix(3.0, 9.0, receiverDepth);\n\tfloat blockerDepthSum = 0.0;\n\tfloat blockerCount = 0.0;\n\n\tfor (int i = 0; i < 8; ++i) {\n\t\tvec2 uv = shadowCoord.xy + (rotation * TEK2_PCSS_DISK[i]) * texel * searchRadiusTexels;\n\t\tfloat blockerDepth = texture(shadowDepthTex, uv).r;\n\n\t\tif (blockerDepth < (receiverDepth - depthBias)) {\n\t\t\tblockerDepthSum += blockerDepth;\n\t\t\tblockerCount += 1.0;\n\t\t}\n\t}\n\n\t// No blocker means fully lit; skip the expensive filter pass.\n\tif (blockerCount < 0.5)\n\t\treturn 1.0;\n\n\tfloat avgBlockerDepth = blockerDepthSum / blockerCount;\n\n\t// Contact-hardening: normalized receiver/blocker separation estimates the\n\t// penumbra ratio. The scale represents the apparent angular size of the sun.\n\tfloat penumbraRatio = max(receiverDepth - avgBlockerDepth, 0.0) / max(avgBlockerDepth, 0.05);\n\tfloat filterRadiusTexels = clamp(0.75 + penumbraRatio * 900.0, 0.75, 18.0);\n\n\tfloat visibility = 0.0;\n\tfor (int i = 0; i < 12; ++i) {\n\t\tvec2 uv = shadowCoord.xy + (rotation * TEK2_PCSS_DISK[i]) * texel * filterRadiusTexels;\n\t\tvisibility += texture(shadowTex, vec3(uv, receiverDepth - depthBias)).r;\n\t}\n\n\treturn visibility / 12.0;\n}\n#endif\n\nvec3 GetShadowMult(vec3 shadowCoord, float NdotL) {\n\t#if (USE_SHADOWS == 1)\n\t\tfloat sh = min(TEK2PCSSShadow(shadowCoord, NdotL), smoothstep(0.0, 0.35, NdotL));\n\t\tvec3 shColor = texture(shadowColorTex, shadowCoord.xy).rgb;\n\t\treturn mix(1.0, sh, shadowDensity.y) * shColor;\n\t#else\n\t\treturn vec3(1.0);\n\t#endif\n}\n'''
)

# ---------------------------------------------------------------------------
# 4) Real PCSS for the advanced SMF terrain receiver.
# ---------------------------------------------------------------------------

smf_frag = ROOT / "cont/base/springcontent/shaders/GLSL/SMFFragProg.glsl"

replace_once(
    smf_frag,
    '''#ifdef HAVE_SHADOWS\n\tuniform sampler2DShadow shadowTex;\n\tuniform sampler2D shadowColorTex;\n\tuniform mat4 shadowMat;\n#endif\n''',
    '''#ifdef HAVE_SHADOWS\n\tuniform sampler2D shadowDepthTex;\n\tuniform sampler2DShadow shadowTex;\n\tuniform sampler2D shadowColorTex;\n\tuniform mat4 shadowMat;\n#endif\n'''
)

replace_once(
    smf_frag,
    '''#ifdef SMF_ADV_SHADING\n\tvec3 GetFragmentNormal(vec2 uv) {\n''',
    '''#ifdef HAVE_SHADOWS\nconst vec2 TEK2_PCSS_DISK[12] = vec2[12](\n\tvec2(-0.326212, -0.405810), vec2(-0.840144, -0.073580),\n\tvec2(-0.695914,  0.457137), vec2(-0.203345,  0.620716),\n\tvec2( 0.962340, -0.194983), vec2( 0.473434, -0.480026),\n\tvec2( 0.519456,  0.767022), vec2( 0.185461, -0.893124),\n\tvec2( 0.507431,  0.064425), vec2( 0.896420,  0.412458),\n\tvec2(-0.321940, -0.932615), vec2(-0.791559, -0.597705)\n);\n\nmat2 TEK2PCSSRotation(vec2 shadowUV, vec2 shadowSize) {\n\tvec2 cell = floor(shadowUV * shadowSize);\n\tfloat angle = fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453) * 6.28318530718;\n\tfloat s = sin(angle);\n\tfloat c = cos(angle);\n\treturn mat2(c, -s, s, c);\n}\n\nfloat TEK2PCSSGroundShadow(vec4 shadowPos, float NdotL) {\n\tvec3 shadowCoord = shadowPos.xyz / shadowPos.w;\n\tvec2 shadowSize = vec2(textureSize(shadowDepthTex, 0));\n\tvec2 texel = 1.0 / shadowSize;\n\tmat2 rotation = TEK2PCSSRotation(shadowCoord.xy, shadowSize);\n\n\tfloat receiverDepth = clamp(shadowCoord.z, 0.0, 1.0);\n\tfloat depthBias = mix(0.00055, 0.00010, clamp(NdotL, 0.0, 1.0));\n\tfloat searchRadiusTexels = mix(3.0, 9.0, receiverDepth);\n\n\tfloat blockerDepthSum = 0.0;\n\tfloat blockerCount = 0.0;\n\tfor (int i = 0; i < 8; ++i) {\n\t\tvec2 uv = shadowCoord.xy + (rotation * TEK2_PCSS_DISK[i]) * texel * searchRadiusTexels;\n\t\tfloat blockerDepth = texture2D(shadowDepthTex, uv).r;\n\n\t\tif (blockerDepth < (receiverDepth - depthBias)) {\n\t\t\tblockerDepthSum += blockerDepth;\n\t\t\tblockerCount += 1.0;\n\t\t}\n\t}\n\n\tif (blockerCount < 0.5)\n\t\treturn 1.0;\n\n\tfloat avgBlockerDepth = blockerDepthSum / blockerCount;\n\tfloat penumbraRatio = max(receiverDepth - avgBlockerDepth, 0.0) / max(avgBlockerDepth, 0.05);\n\tfloat filterRadiusTexels = clamp(0.75 + penumbraRatio * 900.0, 0.75, 18.0);\n\n\tfloat visibility = 0.0;\n\tfor (int i = 0; i < 12; ++i) {\n\t\tvec2 uv = shadowCoord.xy + (rotation * TEK2_PCSS_DISK[i]) * texel * filterRadiusTexels;\n\t\tvisibility += shadow2D(shadowTex, vec3(uv, receiverDepth - depthBias)).r;\n\t}\n\n\treturn visibility / 12.0;\n}\n#endif\n\n#ifdef SMF_ADV_SHADING\n\tvec3 GetFragmentNormal(vec2 uv) {\n'''
)

replace_once(
    smf_frag,
    '''\t\tshadowCoeff = mix(vec3(1.0), shadow2DProj(shadowTex, vertexShadowPos).r * shadowColor, groundShadowDensity);\n''',
    '''\t\tshadowCoeff = mix(vec3(1.0), TEK2PCSSGroundShadow(vertexShadowPos, cosAngleDiffuse) * shadowColor, groundShadowDensity);\n'''
)

print("TEK2 true PCSS patch applied successfully.")
