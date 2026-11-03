# Implementation sequence

The first public media-processing release must support both images and video.
Intermediate PRs are development increments, not a claim of launch readiness.

1. **SDK core (this increment).** Package installation, unsigned provenance records,
   consistent verification results, installed-wheel tests. Related: REQ-003,
   REQ-008, REQ-015; all remain in progress.
2. **Image adapter and reference signing path.** Integrate the selected upstream
   watermark engine after recording code/weight licenses and versions. Exercise
   embedding, extraction, C2PA signing and read-back against actual fixtures.
   Keep watermark payload encoding separate from the full provenance record.
3. **Video path.** Decode, mark, encode, sign and verify actual short/vertical
   videos. Test frame timing, rotation and audio handling; benchmark on CPU.
   Do not call an image-only implementation the first complete release.
4. **Durability and errors.** Recompression, resizing, cropping, metadata loss,
   unmarked controls and corrupted inputs. Record measured quality, false
   positives/negatives, throughput and memory; make failures explicit.
5. **Self-hosted verifier.** Package the same supported checks behind a local
   API/UI, with upload limits and deletion rules. No user account is needed for
   SDK use; hosting operators control access and resource limits.
6. **Requirement profiles and release evidence.** Recheck current official
   sources and applicability, map measures to tests, and publish the coverage
   and limitations of the exact release. Add signing/key operations guidance,
   reproducible builds, examples and deployment instructions.
7. **Landing page and distribution.** Publish supported installation and
   verification workflows, a requirements navigator, and measured examples.

No stage automatically certifies compliance. Legal profiles, real media
bindings, production trust, and privacy controls cannot be inferred from
schema validation alone.
