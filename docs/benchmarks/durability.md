# Durability evidence

REQ-012 remains in progress. A reproducible smoke harness and measured results
are now available: [run instructions](../../benchmarks/durability/README.md),
[release report](../validation/0.2.0a0.md), and
[raw matrix](../validation/results/cpu-smoke-0.2.0a0.json).

The harness covers original files, JPEG recompression, resizing, cropping,
negative controls and H.264 recompression. It records failed transformations
as well as correct recovery. Four synthetic controls are not sufficient to
calibrate FPR/FNR, and no adversarial or statutory durability guarantee follows
from this dataset. Production qualification needs representative content,
scenario-specific acceptance thresholds and broader video-quality testing.
