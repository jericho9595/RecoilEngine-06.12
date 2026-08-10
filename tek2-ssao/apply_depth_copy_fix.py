#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "rts/Rendering/WorldDrawer.cpp"


def replace_once(old: str, new: str) -> None:
    text = WORLD.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one WorldDrawer anchor, found {count}")
    WORLD.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


# Debug mode dedicated to the copied depth texture.  Keep the original AO debug
# switch intact so either stage can be inspected independently.
replace_once(
    'CONFIG(bool, Tek2SSAODebug).defaultValue(false).headlessValue(false).description("Show TEK2 SSAO buffer instead of compositing it");\n',
    'CONFIG(bool, Tek2SSAODebug).defaultValue(false).headlessValue(false).description("Show TEK2 SSAO buffer instead of compositing it");\n'
    'CONFIG(bool, Tek2SSAODebugDepth).defaultValue(false).headlessValue(false).description("Show TEK2 copied opaque depth buffer");\n'
)

# The original experiment blitted depth into a dedicated FBO.  Depth blits are
# sensitive to source/destination depth-format/sample compatibility.  Copy the
# completed opaque framebuffer directly into the already allocated depth texture
# instead; OpenGL selects the depth source because the destination is a depth
# texture.  This also gives us a real GL error if the copy cannot be performed.
replace_once(
    '''\t\tconst std::array<int, 4> srcRect = {\n\t\t\tglobalRendering->viewPosX, globalRendering->viewPosY,\n\t\t\tglobalRendering->viewPosX + tek2SSAOViewX, globalRendering->viewPosY + tek2SSAOViewY\n\t\t};\n\t\tconst std::array<int, 4> dstRect = {0, 0, tek2SSAOViewX, tek2SSAOViewY};\n\t\tif (!FBO::Blit(-1, tek2SSAODepthFBO->GetId(), srcRect, dstRect, GL_DEPTH_BUFFER_BIT, GL_NEAREST))\n\t\t\treturn;\n''',
    '''\t\t// Copy the completed opaque Z-buffer directly into our sampleable depth\n\t\t// texture. This avoids depth-FBO blit format mismatches on Windows.\n\t\tGLint oldReadFBO = 0;\n\t\tGLint currentDrawFBO = 0;\n\t\tglGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &oldReadFBO);\n\t\tglGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &currentDrawFBO);\n\t\tglBindFramebuffer(GL_READ_FRAMEBUFFER, currentDrawFBO);\n\t\tglActiveTexture(GL_TEXTURE0);\n\t\tglBindTexture(GL_TEXTURE_2D, tek2SSAODepthTex);\n\t\twhile (glGetError() != GL_NO_ERROR) {}\n\t\tglCopyTexSubImage2D(\n\t\t\tGL_TEXTURE_2D, 0, 0, 0,\n\t\t\tglobalRendering->viewPosX, globalRendering->viewPosY,\n\t\t\ttek2SSAOViewX, tek2SSAOViewY\n\t\t);\n\t\tconst GLenum depthCopyError = glGetError();\n\t\tglBindTexture(GL_TEXTURE_2D, 0);\n\t\tglBindFramebuffer(GL_READ_FRAMEBUFFER, oldReadFBO);\n\t\tif (depthCopyError != GL_NO_ERROR) {\n\t\t\tstatic bool loggedDepthCopyError = false;\n\t\t\tif (!loggedDepthCopyError) {\n\t\t\t\tLOG_L(L_ERROR, "[TEK2 SSAO] depth copy failed with GL error 0x%X", depthCopyError);\n\t\t\t\tloggedDepthCopyError = true;\n\t\t\t}\n\t\t\treturn;\n\t\t}\n'''
)

# Let the final fullscreen pass visualize the copied depth texture.  Since the
# hardware depth distribution is strongly non-linear, amplify 1-depth so terrain
# and models are visibly distinct instead of almost-white values near 1.0.
replace_once(
    '''uniform sampler2D aoTex;\nvoid main() {\n\tfloat ao = texture(aoTex, vUV).r;\n\tfragColor = vec4(ao, ao, ao, 1.0);\n}\n''',
    '''uniform sampler2D aoTex;\nuniform sampler2D depthTex;\nuniform int debugDepth;\nvoid main() {\n\tif (debugDepth != 0) {\n\t\tfloat d = texture(depthTex, vUV).r;\n\t\tfloat zvis = clamp((1.0 - d) * 512.0, 0.0, 1.0);\n\t\tfragColor = vec4(zvis, zvis, zvis, 1.0);\n\t\treturn;\n\t}\n\tfloat ao = texture(aoTex, vUV).r;\n\tfragColor = vec4(ao, ao, ao, 1.0);\n}\n'''
)

replace_once(
    '''\t\tglActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, tek2SSAOTex[0]);\n\t\tglUniform1i(glGetUniformLocation(tek2SSAOPrograms[2], "aoTex"), 0);\n\n\t\tif (configHandler->GetBool("Tek2SSAODebug")) {\n\t\t\tglDisable(GL_BLEND);\n\t\t} else {\n''',
    '''\t\tglActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, tek2SSAOTex[0]);\n\t\tglUniform1i(glGetUniformLocation(tek2SSAOPrograms[2], "aoTex"), 0);\n\t\tglActiveTexture(GL_TEXTURE1); glBindTexture(GL_TEXTURE_2D, tek2SSAODepthTex);\n\t\tglUniform1i(glGetUniformLocation(tek2SSAOPrograms[2], "depthTex"), 1);\n\t\tconst bool debugAO = configHandler->GetBool("Tek2SSAODebug");\n\t\tconst bool debugDepth = configHandler->GetBool("Tek2SSAODebugDepth");\n\t\tglUniform1i(glGetUniformLocation(tek2SSAOPrograms[2], "debugDepth"), debugDepth ? 1 : 0);\n\n\t\tif (debugAO || debugDepth) {\n\t\t\tglDisable(GL_BLEND);\n\t\t} else {\n'''
)

print("Patched TEK2 SSAO with direct opaque-depth copy and Tek2SSAODebugDepth")
