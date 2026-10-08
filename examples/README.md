# Example Run Results

This directory contains one comparable 60-second run for each supported
bandwidth estimator:

- [`gcc/`](gcc/)
- [`gemini/`](gemini/)
- [`hrcc/`](hrcc/)

All three runs use:

- media: `benchmark/media/Gameplay.mp4`
- trace: `benchmark/traces/fcc_wried/251_HIGH_STABLE.json`
- duration: 60 seconds

Each result directory contains the emulator logs, telemetry, and a derived
`qoe.json` score. The `media`, `trace`, `output_dir`, and `workdir` fields in
`run.json` are rewritten as repository-relative paths after the run so the
archived examples remain portable.

| Model | QoE |
| --- | ---: |
| GCC | 81.644 |
| Gemini | 52.657 |
| HRCC | 59.032 |

## Run the Example

Run from any directory:

```bash
./examples/run_examples.sh
```

New results are written to the ignored `results/example-runs/` directory, so
the archived reference outputs under `examples/` remain unchanged. Set
`OUTPUT_ROOT` to use a different output location:

```bash
OUTPUT_ROOT=/tmp/onl-examples ./examples/run_examples.sh
```

The script refuses to overwrite non-empty result directories. It runs the
models sequentially because all cases share the loopback `tc` configuration.
After each case, it waits five seconds and verifies that the temporary workdir
is unmounted and empty or removed. Pass model names to run only a subset:

```bash
./examples/run_examples.sh hrcc
```

The run requires the same Linux, Git LFS, FFmpeg, `tc`, tmpfs, and `sudo`
dependencies documented in the repository root README.

## Recalculate QoE

```bash
python3 benchmark/calculate_qoe.py examples/gcc
python3 benchmark/calculate_qoe.py examples/gemini
python3 benchmark/calculate_qoe.py examples/hrcc
```
