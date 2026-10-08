# ONL Emulator Evaluation

This repository contains a trace-driven evaluation workflow for real-time
communication bandwidth-estimation algorithms. It combines a prebuilt
AlphaRTC runtime, adapted Gemini and HRCC estimators, network traces, benchmark
media, and a local experiment runner.

The fixed evaluation matrix contains five representative RTC media workloads
and 120 network traces in 18 dataset/category classes, producing 600
media-trace cases for each evaluated estimator.

## Repository Layout

| Path | Contents |
| --- | --- |
| [`alphartc/`](alphartc/) | Prebuilt AlphaRTC runtime and Python inference adapter |
| [`models/`](models/) | Vendored and adapted Gemini and HRCC estimators |
| [`data/`](data/) | Media URL catalog and full network-trace source pool |
| [`benchmark/`](benchmark/) | Fixed media and trace benchmark suite |
| [`emulator_call/`](emulator_call/) | End-to-end local experiment runner |
| `results/` | Local experiment output; ignored by Git |

## Model Provenance and Adaptation

The code under [`models/`](models/) is maintained directly in this repository
rather than as Git submodules. It is based on OpenNetLab's
[AlphaRTC challenge example](https://github.com/OpenNetLab/Challenge-Example)
and related Gemini and HRCC estimator implementations, then adapted for this
evaluation workflow.

The local changes primarily integrate both estimators with the same AlphaRTC
Python inference contract:

- each model directory exposes `BandwidthEstimator.py`;
- the module exports an `Estimator` class;
- `report_states(stats)` receives per-packet metadata;
- `get_estimated_bandwidth()` returns a target bitrate in bits per second;
- model paths are resolved relative to the checked-in model directory; and
- [`emulator_call/`](emulator_call/) selects the implementation through
  `--model gemini` or `--model hrcc`.

The default model artifacts are:

| Model | Default artifact |
| --- | --- |
| Gemini | `models/Gemini/model/ppo_2021_07_20_09_15_37.pth` |
| HRCC | `models/HRCC/ppo_2021_07_25_04_57_11_with500trace.pth` |

These implementations require PyTorch and NumPy. The checked-in artifacts were
verified with Python 3.8.10, PyTorch 2.4.1, and NumPy 1.24.4. These versions
describe the verified environment and are not strict dependency pins.

## Requirements

- 64-bit Linux
- Python 3.8 or newer
- PyTorch and NumPy for Gemini and HRCC
- FFmpeg and FFprobe
- `tc` from iproute2
- `mount`, `mountpoint`, `umount`, and `sudo`
- Git LFS

Install Git LFS and retrieve binary, media, and model assets:

```bash
git lfs install
git lfs pull
```

Only load model artifacts from trusted sources. PyTorch checkpoints can use
Python object deserialization.

## Run the Benchmark

Run commands from the repository root:

```bash
python3 run_benchmark.py \
  --models gcc gemini hrcc \
  --duration 60 \
  --workdir workdir \
  --results-dir results \
  --resume
```

The benchmark runner discovers the fixed media and traces, executes cases
sequentially, and stores results under
`results/<model>/<media>/<dataset>/<trace>/`. Use `--dry-run` to verify the
selected case count without starting an experiment. Filters are available
through `--media`, `--datasets`, and `--categories`.

Cases cannot run concurrently because they share the loopback `tc`
configuration. The runner requires `sudo` and should run on an isolated
evaluation host.

To run one case directly:

```bash
python3 -m emulator_call \
  --trace benchmark/traces/fcc_wried/105_LOW_STABLE.json \
  --media benchmark/media/Gameplay.mp4 \
  --duration 60 \
  --output-dir results/gcc-example \
  --workdir workdir \
  --model gcc
```

See [`emulator_call/README.md`](emulator_call/README.md) for detailed runtime,
privilege, input, and output documentation. See
[`alphartc/README.md`](alphartc/README.md) for the prebuilt runtime and custom
estimator interface. Dataset provenance and field definitions are documented
in [`data/README.md`](data/README.md).

## Calculate QoE

After a successful run, calculate its reference score from `telemetry.json`.
The calculator reads `run.json` from the same result directory:

```bash
python3 benchmark/calculate_qoe.py \
  results/gemini-example/telemetry.json
```

The score is the equally weighted mean of three normalized components:

```text
bitrate = min(1, received bitrate / min(mean trace capacity, source bitrate))
jitter  = max(0, 1 - jitter-buffer delay / 150 ms)
freeze  = max(0, 1 - freeze duration / call duration)
QoE     = 100 * (bitrate + jitter + freeze) / 3
```

Mean trace capacity is weighted by segment duration. The calculator reports
the total QoE and all three components as JSON.

## Aggregate Benchmark Results

To prevent unequal class sizes from changing class weights:

1. calculate QoE for each individual run;
2. average media and trace results within each of the 18 network classes; and
3. report the macro-average across the 18 class means.

Use the same 600-case set, call duration, and aggregation procedure for every
estimator being compared. The trace distribution is documented in
[`benchmark/traces/README.md`](benchmark/traces/README.md), and the media
characteristics and attribution are documented in
[`benchmark/media/README.md`](benchmark/media/README.md).

## License and Upstream Code

The repository is distributed under the [BSD 3-Clause License](LICENSE).
Vendored or adapted upstream components and datasets remain subject to their
respective attribution, license, and usage terms.
