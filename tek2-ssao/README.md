# TEK2 engine SSAO experiment

Isolated from the PCSS branch and based on Recoil `2026.06.12`.

## Design
- engine-level post process in `CWorldDrawer`
- copies the completed opaque depth buffer so terrain, units and features participate
- reconstructs view-space position and normals from depth
- half-resolution SSAO buffer
- 8 / 12 / 16 hemisphere samples for low / medium / high quality
- two-pass depth-aware bilateral blur to limit black halos and edge bleeding
- multiplicative composite before transparent objects
- no changes to simulation, shadow generation or game Lua

## Config
```text
Tek2SSAO=1
Tek2SSAOQuality=1
Tek2SSAORadius=4.0
Tek2SSAOStrength=1.0
Tek2SSAODebug=0
```

Quality values: `0=8`, `1=12`, `2=16` AO samples. The branch defaults to enabled because it is an isolated test build.

Disable the old Lua SSAO widget while comparing this engine implementation to avoid double ambient occlusion.
