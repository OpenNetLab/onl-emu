#!/usr/bin/env bash

# Run the archived example case for each selected bandwidth estimator.

set -u

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
examples_dir="$project_root/examples"
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
    local model="$1"
    python3 - "$examples_dir/$model/run.json" "$model" <<'PY'
import json
import sys
from pathlib import Path

run_path = Path(sys.argv[1])
model = sys.argv[2]
run = json.loads(run_path.read_text(encoding="utf-8"))
run["trace"] = "../../benchmark/traces/fcc_wried/251_HIGH_STABLE.json"
run["media"] = "../../benchmark/media/Gameplay.mp4"
run["output_dir"] = f"examples/{model}"
run["workdir"] = "workdir"
run_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
PY
}

calculate_qoe() {
    local model="$1"
    local output_dir="$examples_dir/$model"
    local temporary="$output_dir/qoe.json.tmp"
    python3 "$project_root/benchmark/calculate_qoe.py" \
        "$output_dir" >"$temporary" &&
        mv -- "$temporary" "$output_dir/qoe.json"
}

for model in "${models[@]}"; do
    output_dir="$examples_dir/$model"
    if [[ -d "$output_dir" ]] &&
        find "$output_dir" -mindepth 1 -print -quit | grep -q .; then
        echo "refusing to overwrite non-empty output: $output_dir" >&2
        exit 1
    fi
done

check_workdir

cd -- "$project_root"
for model in "${models[@]}"; do
    output_dir="$examples_dir/$model"
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
    normalize_run_metadata "$model"
    calculate_qoe "$model" || {
        echo "failed to calculate QoE for $model" >&2
        exit 1
    }
done

echo "All example runs completed successfully"
