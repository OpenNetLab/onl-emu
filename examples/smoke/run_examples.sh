#!/usr/bin/env bash

# Run the archived example case for each selected bandwidth estimator.

set -u

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
output_root="${OUTPUT_ROOT:-$project_root/results/example-runs}"
workdir="$project_root/workdir"
media="$project_root/benchmark/media/Gameplay.mp4"
trace="$project_root/benchmark/traces/fcc_wried/251_HIGH_STABLE.json"
duration=60
cooldown_seconds=5
supported_models=(gcc gemini hrcc)
models=("${supported_models[@]}")

if [[ "$#" -gt 0 ]]; then
    models=("$@")
fi

for model in "${models[@]}"; do
    supported=false
    for candidate in "${supported_models[@]}"; do
        if [[ "$model" == "$candidate" ]]; then
            supported=true
            break
        fi
    done
    if [[ "$supported" != true ]]; then
        echo "unsupported model: $model" >&2
        exit 2
    fi
done

check_workdir() {
    if mountpoint -q -- "$workdir"; then
        echo "workdir is still mounted: $workdir" >&2
        return 1
    fi
    if [[ -e "$workdir" ]]; then
        if [[ ! -d "$workdir" ]]; then
            echo "workdir is not a directory: $workdir" >&2
            return 1
        fi
        if find "$workdir" -mindepth 1 -print -quit | grep -q .; then
            echo "workdir contains residual files: $workdir" >&2
            return 1
        fi
    fi
}

normalize_run_metadata() {
    local output_dir="$1"
    python3 - \
        "$output_dir/run.json" \
        "$project_root" \
        "$trace" \
        "$media" \
        "$output_dir" \
        "$workdir" <<'PY'
import json
import os
import sys
from pathlib import Path

run_path = Path(sys.argv[1])
project_root = Path(sys.argv[2])
trace = Path(sys.argv[3])
media = Path(sys.argv[4])
output_dir = Path(sys.argv[5])
workdir = Path(sys.argv[6])
run = json.loads(run_path.read_text(encoding="utf-8"))
run["trace"] = os.path.relpath(trace, output_dir)
run["media"] = os.path.relpath(media, output_dir)
run["output_dir"] = os.path.relpath(output_dir, project_root)
run["workdir"] = os.path.relpath(workdir, project_root)
run_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
PY
}

calculate_qoe() {
    local output_dir="$1"
    local temporary="$output_dir/qoe.json.tmp"
    if python3 "$project_root/benchmark/calculate_qoe.py" \
        "$output_dir" >"$temporary"; then
        mv -- "$temporary" "$output_dir/qoe.json"
    else
        rm -f -- "$temporary"
        return 1
    fi
}

for model in "${models[@]}"; do
    output_dir="$output_root/$model"
    if [[ -d "$output_dir" ]] &&
        find "$output_dir" -mindepth 1 -print -quit | grep -q .; then
        echo "refusing to overwrite non-empty output: $output_dir" >&2
        exit 1
    fi
done

check_workdir

cd -- "$project_root"
for model in "${models[@]}"; do
    output_dir="$output_root/$model"
    echo "Running $model example"
    python3 -m emulator_call \
        --trace "$trace" \
        --media "$media" \
        --duration "$duration" \
        --output-dir "$output_dir" \
        --workdir "$workdir" \
        --model "$model"
    run_status=$?

    echo "Cooling down for $cooldown_seconds seconds"
    sleep "$cooldown_seconds"
    check_workdir || exit 1

    if [[ "$run_status" -ne 0 ]]; then
        echo "$model example failed with exit code $run_status" >&2
        exit "$run_status"
    fi
    normalize_run_metadata "$output_dir"
    calculate_qoe "$output_dir" || {
        echo "failed to calculate QoE for $model" >&2
        exit 1
    }
done

echo "All example runs completed successfully"
