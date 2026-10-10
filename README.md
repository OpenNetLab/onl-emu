# ONL Emulator Evaluation

An AlphaRTC-based emulator and reproducible benchmark for evaluating
real-time communication bandwidth-estimation (BWE) algorithms under controlled
media and network conditions.

The fixed benchmark combines five RTC media workloads with 120 network traces
in 18 network classes. This produces 600 cases per estimator and 1,800 cases
for the included GCC, Gemini, and HRCC estimators.

## Quick Start

### 1. Prepare the environment

The evaluation runs on 64-bit Linux and requires:

- Python 3.8 or newer
- PyTorch and NumPy for Gemini and HRCC
- FFmpeg and FFprobe
- `tc` from iproute2
- `mount`, `mountpoint`, `umount`, and `sudo`
- Git LFS

Retrieve the prebuilt runtime, model weights, media, and example logs:

```bash
git lfs install
git lfs pull
```

The runner changes the loopback `tc` configuration and mounts a temporary
tmpfs. Run it on an isolated evaluation host where `sudo` is available.

### 2. Inspect or rerun the example

[`examples/smoke/`](examples/smoke/) contains comparable 60-second GCC,
Gemini, and HRCC runs with raw logs, telemetry, and QoE scores.

Run the same case locally:

```bash
./examples/smoke/run_examples.sh
```

New output is written to `results/example-runs/smoke/`; the archived reference
results are not overwritten. See
[`examples/smoke/README.md`](examples/smoke/README.md) for the fixed inputs and
recorded scores.

### 3. Run one case

```bash
python3 -m emulator_call \
  --trace benchmark/traces/fcc_wried/105_LOW_STABLE.json \
  --media benchmark/media/Gameplay.mp4 \
  --duration 60 \
  --output-dir results/gcc-example \
  --workdir workdir \
  --model gcc
```

The supported model names are `default`, `gcc`, `gemini`, and `hrcc`.
Omitting `--model` selects `default`, the AlphaRTC Python estimator that
returns a fixed 2 Mbit/s bandwidth estimate. An unsupported model name prints
an error and exits without starting a call.

## Reproduce Section 4.5/Fig. 11

The three 60-second Screen-sharing cases use:

| Panel | Estimator | Trace and network condition |
| --- | --- | --- |
| (a) | Default fixed 2 Mbit/s BWE | `data/traces/random_loss/real/20210515_1730_REAL_NODE.json`; effectively unconstrained capacity with random loss |
| (b) | GCC | `data/traces/random_loss/synthetic/STABLE_HIGH_CRTT_RANDOMLOSS_00.json`; fixed 2 Mbit/s capacity with random loss |
| (c) | Gemini | `data/traces/random_loss/synthetic/STABLE_HIGH_CRTT_RANDOMLOSS_00.json`; fixed 2 Mbit/s capacity with random loss |

Run all three cases:

```bash
./examples/fig11/run_fig11_random_loss.sh
```

Set `DRY_RUN=1` to print the exact emulator commands without running them:

```bash
DRY_RUN=1 ./examples/fig11/run_fig11_random_loss.sh
```

For example, panel (a) runs:

```bash
python3 -m emulator_call \
  --trace data/traces/random_loss/real/20210515_1730_REAL_NODE.json \
  --media benchmark/media/Screen-sharing.mp4 \
  --duration 60 \
  --output-dir results/example-runs/fig11-random-loss/a \
  --workdir workdir
```

The corresponding archived logs, telemetry, metadata, and plots are under
[`examples/fig11/a/`](examples/fig11/a/),
[`examples/fig11/b/`](examples/fig11/b/), and
[`examples/fig11/c/`](examples/fig11/c/). See
[`examples/fig11/README.md`](examples/fig11/README.md) for details and
[`data/README.md`](data/README.md) for random-loss trace provenance.

## Run the Full Benchmark

Run all 600 cases for each selected model:

```bash
python3 run_benchmark.py \
  --models gcc gemini hrcc \
  --duration 60 \
  --workdir workdir \
  --results-dir results \
  --resume
```

Results are stored under:

```text
results/<model>/<media>/<dataset>/<trace>/
```

Useful options:

- `--dry-run`: print the selected case count without running
- `--resume`: skip cases whose `run.json` status is `success`
- `--fail-fast`: stop after the first failed case
- `--media`: select media workloads
- `--datasets`: select trace datasets
- `--categories`: select network classes

Cases run sequentially because they share the loopback `tc` configuration.
After every attempted case, the runner waits five seconds and verifies that
the workdir is unmounted and empty or removed. Incomplete cleanup aborts the
benchmark rather than contaminating later cases.

## Results and QoE

Each successful output directory contains:

- `run.json`: inputs, model, timestamps, status, and process result
- `telemetry.json`: extracted receiver metrics
- `receiver.log` and `sender.log`: AlphaRTC metrics
- `receiver_process.log` and `sender_process.log`: process output

Calculate the reference QoE for one result:

```bash
python3 benchmark/calculate_qoe.py results/gcc-example
```

The score is the equally weighted mean of three normalized components:

```text
bitrate = min(1, received bitrate / min(mean trace capacity, source bitrate))
jitter  = max(0, 1 - jitter-buffer delay / 150 ms)
freeze  = max(0, 1 - freeze duration / call duration)
QoE     = 100 * (bitrate + jitter + freeze) / 3
```

Mean trace capacity is weighted by segment duration. For benchmark reporting:

1. calculate QoE for each run;
2. average media and trace results within each of the 18 network classes; and
3. report the macro-average across the 18 class means.

Use the same case set, call duration, and aggregation procedure for every
estimator being compared.

## Repository Contents

| Path | Contents |
| --- | --- |
| [`alphartc/`](alphartc/) | Prebuilt AlphaRTC runtime and Python inference adapter |
| [`models/`](models/) | Adapted Gemini and HRCC estimators and model artifacts |
| [`data/`](data/) | Media URL catalog and full network-trace source pool |
| [`benchmark/`](benchmark/) | Fixed media suite, 120 traces, and QoE calculator |
| [`emulator_call/`](emulator_call/) | Single-case preparation and execution engine |
| [`examples/`](examples/) | Archived GCC, Gemini, and HRCC example outputs |
| [`run_benchmark.py`](run_benchmark.py) | Sequential fixed-benchmark runner |

## Models and Data

The code under [`models/`](models/) is maintained directly in this repository.
It is based on OpenNetLab's
[AlphaRTC challenge example](https://github.com/OpenNetLab/Challenge-Example)
and related Gemini and HRCC implementations, then adapted to a common Python
inference interface:

- `report_states(stats)` receives per-packet metadata;
- `get_estimated_bandwidth()` returns the target bitrate in bits per second;
- model artifacts are resolved relative to each model directory; and
- the runner selects an estimator with `--model`.

The checked-in model artifacts were verified with Python 3.8.10, PyTorch
2.4.1, and NumPy 1.24.4. These are verification versions, not strict pins.
Only load PyTorch model artifacts from trusted sources.

The source pool contains FCC wired, Norway 3G, mmWave 5G, and derived
random-loss traces. The fixed benchmark selects 120 traces from the three
public network datasets and pairs them with five representative media files.

## Detailed Documentation

- [`examples/smoke/README.md`](examples/smoke/README.md): archived smoke-test
  inputs, scores, and rerun instructions
- [`examples/fig11/README.md`](examples/fig11/README.md): archived Fig. 11
  inputs, results, and rerun instructions
- [`emulator_call/README.md`](emulator_call/README.md): runtime behavior,
  privileges, inputs, and outputs
- [`alphartc/README.md`](alphartc/README.md): prebuilt runtime and custom
  estimator interface
- [`data/README.md`](data/README.md): dataset provenance and trace fields
- [`benchmark/traces/README.md`](benchmark/traces/README.md): fixed trace
  distribution and aggregation
- [`benchmark/media/README.md`](benchmark/media/README.md): media
  characteristics and attribution

## License

This repository is distributed under the [BSD 3-Clause License](LICENSE).
Vendored or adapted upstream components, model artifacts, media, and datasets
remain subject to their respective attribution, license, and usage terms.
