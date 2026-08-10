#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SHADERS = [
    ROOT / "cont/base/springcontent/shaders/GLSL/ModelFragProgGL4.glsl",
    ROOT / "cont/base/springcontent/shaders/GLSL/SMFFragProg.glsl",
]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    print(f"Tuned {path.relative_to(ROOT)}")


for shader in SHADERS:
    # PCSS V3 tuning: use 2048 as the visual reference.  At 4096 the kernel
    # grows to 2x as many texels, preserving roughly the same penumbra width in
    # shadow UV/world space while retaining the extra edge/detail resolution.
    replace_once(
        shader,
        "\tfloat searchRadiusTexels = mix(3.0, 9.0, receiverDepth);\n",
        "\tfloat resolutionScale = max(max(shadowSize.x, shadowSize.y) / 2048.0, 0.5);\n"
        "\tfloat searchRadiusTexels = mix(3.0, 9.0, receiverDepth) * resolutionScale;\n",
    )

    replace_once(
        shader,
        "\tfloat filterRadiusTexels = clamp(0.75 + penumbraRatio * 900.0, 0.75, 18.0);\n",
        "\tfloat filterRadiusTexels = clamp(\n"
        "\t\t(0.75 + penumbraRatio * 900.0) * resolutionScale,\n"
        "\t\t0.75 * resolutionScale,\n"
        "\t\t18.0 * resolutionScale\n"
        "\t);\n",
    )

print("TEK2 PCSS V3: resolution-independent 2048-reference penumbra tuning applied")
