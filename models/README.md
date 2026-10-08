# Bandwidth Estimator Models

This directory contains the Python bandwidth estimators and pretrained model
artifacts used by the emulator.

## Available Models

| Emulator name | Directory | Default artifact |
| --- | --- | --- |
| `gemini` | [`Gemini/`](Gemini/) | `Gemini/model/ppo_2021_07_20_09_15_37.pth` |
| `hrcc` | [`HRCC/`](HRCC/) | `HRCC/ppo_2021_07_25_04_57_11_with500trace.pth` |

Each directory exposes a `BandwidthEstimator.py` module containing an
`Estimator` class. AlphaRTC calls:

- `report_states(stats)` once for each received packet
- `get_estimated_bandwidth()` approximately once per feedback interval

The returned bandwidth is measured in bits per second.

## Requirements

Both implementations require Python, PyTorch, and NumPy. The evaluation
environment used to verify the checked-in artifacts had:

```text
Python 3.8.10
PyTorch 2.4.1
NumPy 1.24.4
```

These are verification versions, not strict dependency pins. The models
originate from older AlphaRTC challenge code and may also run with earlier
compatible releases.

Model artifacts are stored with Git LFS. Retrieve them after cloning:

```bash
git lfs install
git lfs pull --include="models/**"
```

Only load model artifacts from a trusted source. PyTorch model loading can
deserialize executable Python objects, particularly with older checkpoints and
older PyTorch loading behavior.

## Emulator Integration

The project runner selects the estimator with `--model`:

```bash
python3 -m emulator_call \
  --trace data/traces/fcc_wried/0_MIXED_STABLE.json \
  --media benchmark/media/Gameplay.mp4 \
  --duration 60 \
  --output-dir results/gemini-example \
  --workdir workdir \
  --model gemini
```

For Python-based models, the runner sets `ALPHARTC_ESTIMATOR_DIR` to the
selected directory. The AlphaRTC adapter then loads that directory's
`BandwidthEstimator.py`.

The estimators can also be selected when invoking the AlphaRTC wrapper
directly:

```bash
LD_LIBRARY_PATH="$PWD/alphartc/dll${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
ALPHARTC_ESTIMATOR_DIR="$PWD/models/Gemini" \
  python3 alphartc/pyinfer/peerconnection_serverless \
  /path/to/peer_config.json
```

## Additional Artifacts

The Gemini directory includes older checkpoints retained for comparison and
its original challenge example documentation. The HRCC directory includes an
ONNX export, but the default `BandwidthEstimator.py` loads the PyTorch `.pth`
checkpoint listed above.
