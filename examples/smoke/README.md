# Smoke Example Outputs

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

The QoE score and its normalized components are:

| Model | QoE (0-100) | Bitrate score | Jitter score | Freeze score |
| --- | ---: | ---: | ---: | ---: |
| GCC | 81.644 | 0.645 | 0.820 | 0.985 |
| Gemini | 52.657 | 0.146 | 0.453 | 0.981 |
| HRCC | 59.032 | 0.258 | 0.513 | 1.000 |

The receiver telemetry underlying those scores is:

| Model | Received bitrate (Kbit/s) | Jitter-buffer delay (ms) | Freeze duration (ms) | Frames decoded | Dropped frames | Render FPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GCC | 1306 | 27 | 916 | 3536 | 6 | 59 |
| Gemini | 295 | 82 | 1153 | 2417 | 5 | 40 |
| HRCC | 522 | 73 | 0 | 3170 | 4 | 53 |

## Run the Example

Run from any directory:

```bash
./examples/smoke/run_examples.sh
```

New results are written to the ignored `results/example-runs/smoke/`
directory, so the archived reference outputs under `examples/smoke/` remain
unchanged. Set `OUTPUT_ROOT` to use a different output location:

```bash
OUTPUT_ROOT=/tmp/onl-examples ./examples/smoke/run_examples.sh
```

The script refuses to overwrite non-empty result directories. It runs the
models sequentially because all cases share the loopback `tc` configuration.
After each case, it waits five seconds and verifies that the temporary workdir
is unmounted and empty or removed. Pass model names to run only a subset:

```bash
./examples/smoke/run_examples.sh hrcc
```

The run requires the same Linux, Git LFS, FFmpeg, `tc`, tmpfs, and `sudo`
dependencies documented in the repository root README.

## Recalculate QoE

```bash
python3 benchmark/calculate_qoe.py examples/smoke/gcc
python3 benchmark/calculate_qoe.py examples/smoke/gemini
python3 benchmark/calculate_qoe.py examples/smoke/hrcc
```
