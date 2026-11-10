# Reliability evaluation protocol

The external 0.7.1a1 review on 9 November 2026 tested 22 clean 720p clips
(stock and synthetic) with the production Node blind scanner: 22 scoped
`not_found` results, no recovered ID. Four marked positive controls recovered
their expected ID. Raw E1/E1b observations are preserved here. These are
carried-forward research results for 0.7.1a1, not a new 0.7.1a2 benchmark.

```sh
# Provisioned Linux media environment; execute on the test server.
python benchmarks/reliability/evaluate.py CLEAN_DIR POSITIVE_DIR results.jsonl
python benchmarks/reliability/miscorrection.py POSITIVE_DIR miscorrection.jsonl
```

Read the script headers before running. They also explore random BCH words
and correlated subsets with a Python reference decoder; those are auxiliary
research, not a replacement for the production Node outcome. Positive file
names begin with the receipt ID followed by `__`; that ID is used only for
post-decode scoring, never passed to `scan_video`.

## Interpretation limits

- Zero failures on 22 purpose-selected clips does not establish a population
  FPR or a probability for any particular static image. Uniform-bit estimates
  are model assumptions, not measured deployment rates.
- Thousands of overlapping/correlated hypotheses from those same clips are
  not thousands of independent samples. Ordinary binomial confidence bounds
  need justified sampling/independence assumptions.
- Two matching direct reads are concordant observations, not independent
  statistical evidence on a static/repeated scene. A recovered ID does not
  authenticate the whole file or the factual source.
- On one marked clip Node accepted 18 phase hypotheses versus Python's 14;
  all accepted IDs were correct. Cause is unproven. Node stores aggregate
  totals in `Float32Array` too; calling it a float64 accumulator is inaccurate.
  Reference-decoder acceptance must not be substituted for production FPR.
- E1b observed other valid BCH codewords that the prefix rejected. Canonical
  BCH validation and the fixed prefix are useful guards, not cryptographic
  authentication or a proof that wrong attribution is impossible.

For deployment calibration use a held-out, representative clean corpus, the
actual production engine/budgets and transformations, and marked positives.
Report per-asset results, incomplete searches and wrong IDs separately. GPU
remover costs and a unified ONNX implementation remain unmeasured hypotheses;
CPU attack timing is not a universal lower bound for an attacker.
