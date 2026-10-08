# Emulator Call Runner

`emulator_call` runs one trace-driven AlphaRTC call on the local machine. It
prepares the media and peer configurations, replays a network trace on the
loopback interface, starts receiver and sender processes, extracts receiver
telemetry, and exports the run artifacts.

## Requirements

- Linux with `tc` from iproute2
- Python 3.8 or newer
- FFmpeg and FFprobe
- `mount`, `mountpoint`, and `umount`
- `sudo` permission to mount tmpfs and configure the loopback interface
- AlphaRTC runtime files under [`../alphartc/`](../alphartc/)
- Model files under [`../models/`](../models/) when using Gemini or HRCC

Install Git LFS and retrieve the runtime and model assets before running an
experiment:

```bash
git lfs install
git lfs pull
```

The input media must contain both a video stream and an audio stream. It must
be at least as long as the requested call duration, and its video dimensions
must be positive even numbers.

## Run an Experiment

Run commands from the repository root:

```bash
python3 -m emulator_call \
  --trace data/traces/fcc_wried/0_MIXED_STABLE.json \
  --media benchmark/media/Gameplay.mp4 \
  --duration 60 \
  --output-dir results/gcc-example \
  --workdir workdir \
  --model gcc
```

`--model` accepts:

- `gcc`: built-in AlphaRTC GCC estimator
- `gemini`: Python estimator from `models/Gemini`
- `hrcc`: Python estimator from `models/HRCC`

The output directory must be absent or empty. The work directory must also be
empty and must not contain, or be contained by, the output directory.

## What the Runner Does

1. Mounts a 24GB tmpfs at the requested work directory.
2. Uses FFmpeg to convert the source media into AlphaRTC video and audio
   inputs.
3. Generates sender and receiver serverless configurations.
4. Applies each `uplink.trace_pattern` entry to the loopback interface with
   Linux `tc`.
5. Starts the receiver, followed by the sender.
6. Extracts receiver telemetry and copies persistent artifacts to the output
   directory.
7. Stops child processes, removes the `tc` configuration, and unmounts the
   temporary work directory.

The tmpfs size is an upper limit; ensure the host has enough memory or swap for
the uncompressed media generated during the run.

## Output

Each output directory contains:

| File | Description |
| --- | --- |
| `run.json` | Run status, input paths, timestamps, model, and process result |
| `telemetry.json` | Final receiver telemetry values extracted from AlphaRTC |
| `receiver.log` | AlphaRTC receiver metrics log |
| `sender.log` | AlphaRTC sender metrics log |
| `receiver_process.log` | Receiver process stdout and stderr |
| `sender_process.log` | Sender process stdout and stderr |

On failure, `run.json` records the exception type and message. Files generated
before the failure are exported when available.

## Network Scope and Privileges

The current implementation applies shaping to the local loopback interface
`lo`; it is intended for sender and receiver processes running on the same
host. Because changing `tc` state affects other loopback traffic, use an
isolated evaluation host and do not run multiple emulator calls concurrently.

The process invokes `sudo` for both tmpfs management and `tc`. Configure the
host so these commands can run for the duration of the experiment. If a run is
interrupted and cleanup cannot finish, inspect the loopback qdisc and workdir
mount before starting another run:

```bash
tc qdisc show dev lo
mountpoint workdir
```

## Python API

The package exports `run_emulator`:

```python
from pathlib import Path

from emulator_call import run_emulator

result = run_emulator(
    trace=Path("data/traces/fcc_wried/0_MIXED_STABLE.json"),
    media=Path("benchmark/media/Gameplay.mp4"),
    duration=60,
    output_dir=Path("results/gcc-example"),
    workdir=Path("workdir"),
    model="gcc",
)
```
