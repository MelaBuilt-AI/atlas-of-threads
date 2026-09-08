# Terrain color textures

Ten user-supplied 4096 × 4096 sRGB PNGs, created for Atlas of Threads, 2026-09-07.
These are unchanged Lanczos-upscaled copies of the original 1254 × 1254 generated
images. The upscale adds no original detail; these contain color only, with no
normal, displacement, or roughness maps. Use mirrored repeat on both axes.

The renderer tiles in stable world coordinates at 12 scene units per tile and
keeps only the current surface loaded. A browser-local random assignment gives
each Threadwalk a stable surface, choosing among the least-used textures so
all ten appear before a new assignment repeats. This is visual presentation,
not a graph annotation or a synchronized cross-device identity.
