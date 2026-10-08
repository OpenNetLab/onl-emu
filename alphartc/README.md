# AlphaRTC Runtime

This directory contains the prebuilt AlphaRTC runtime used by the emulator.
The binaries target 64-bit Linux and are stored with Git LFS.

## Layout

```text
alphartc/
|-- dll/       ONNX inference and ONNX Runtime shared libraries
|-- exe/       GCC and Python-inference peer connection executables
`-- pyinfer/   Python wrapper and bandwidth-estimator adapter
```

The two executable entry points serve different estimators:

- `exe/peerconnection_gcc` runs the built-in GCC estimator.
- `pyinfer/peerconnection_serverless` starts
  `exe/peerconnection_serverless_pyinfer` and exchanges packet statistics and
  bandwidth estimates with a Python `Estimator`.

## Retrieve the Runtime

Install Git LFS before cloning or pulling the runtime files:

```bash
git lfs install
git lfs pull --include="alphartc/**"
```

Verify that the executable files are present rather than LFS pointer files:

```bash
file alphartc/exe/peerconnection_gcc
file alphartc/exe/peerconnection_serverless_pyinfer
```

Both commands should report 64-bit ELF files.

## Run a Peer

Each entry point expects an AlphaRTC serverless JSON configuration as its
first argument.

Run the built-in GCC estimator:

```bash
alphartc/exe/peerconnection_gcc /path/to/peer_config.json
```

Run the default Python estimator:

```bash
LD_LIBRARY_PATH="$PWD/alphartc/dll${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  python3 alphartc/pyinfer/peerconnection_serverless \
  /path/to/peer_config.json
```

The project-level `emulator_call` module normally prepares these configuration
files, sets the required environment, and starts both peers.

## Use a Custom Python Estimator

Set `ALPHARTC_ESTIMATOR_DIR` to a directory containing
`BandwidthEstimator.py`. That module must export an `Estimator` class with the
following interface:

```python
class Estimator:
    def report_states(self, stats: dict):
        ...

    def get_estimated_bandwidth(self):
        ...
```

`get_estimated_bandwidth()` must return the target bitrate in bits per second.

```bash
LD_LIBRARY_PATH="$PWD/alphartc/dll${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
ALPHARTC_ESTIMATOR_DIR="$PWD/models/Gemini" \
  python3 alphartc/pyinfer/peerconnection_serverless \
  /path/to/peer_config.json
```

## Runtime Dependencies

The prebuilt runtime requires a compatible 64-bit Linux system, Python 3 for
Python-based estimators, and the system libraries reported by `ldd`. The ONNX
libraries in `dll/` must be available through `LD_LIBRARY_PATH` when using the
Python-inference executable.
