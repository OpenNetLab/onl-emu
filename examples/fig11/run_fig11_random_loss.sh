#!/usr/bin/env bash

# Run the Section 4.5/Fig. 11 trace with default, GCC, and Gemini estimators.

set -u

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
output_root="${OUTPUT_ROOT:-$project_root/results/example-runs/fig11-random-loss}"
workdir="$project_root/workdir"
media="$project_root/benchmark/media/Screen-sharing.mp4"
real_trace="$project_root/data/traces/random_loss/real/20210515_1730_REAL_NODE.json"
synthetic_trace="$project_root/data/traces/random_loss/synthetic/STABLE_HIGH_CRTT_RANDOMLOSS_00.json"
duration=60
cooldown_seconds=5
dry_run="${DRY_RUN:-0}"
supported_cases=(a b c)
cases=("${supported_cases[@]}")

if [[ "$#" -gt 0 ]]; then
  cases=("$@")
fi

for case_name in "${cases[@]}"; do
  supported=false
  for candidate in "${supported_cases[@]}"; do
    if [[ "$case_name" == "$candidate" ]]; then
      supported=true
      break
    fi
  done
  if [[ "$supported" != true ]]; then
    echo "unsupported case: $case_name" >&2
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

if [[ "$dry_run" != "1" ]]; then
  for case_name in "${cases[@]}"; do
    output_dir="$output_root/$case_name"
    if [[ -d "$output_dir" ]] &&
      find "$output_dir" -mindepth 1 -print -quit | grep -q .; then
      echo "refusing to overwrite non-empty output: $output_dir" >&2
      exit 1
    fi
  done

  check_workdir
  cd -- "$project_root"
fi

for case_name in "${cases[@]}"; do
  output_dir="$output_root/$case_name"
  case "$case_name" in
    a)
      model=default
      trace="$real_trace"
      ;;
    b)
      model=gcc
      trace="$synthetic_trace"
      ;;
    c)
      model=gemini
      trace="$synthetic_trace"
      ;;
  esac
  command=(
    python3 -m emulator_call
    --trace "$trace"
    --media "$media"
    --duration "$duration"
    --output-dir "$output_dir"
    --workdir "$workdir"
  )
  if [[ "$model" != "default" ]]; then
    command+=(--model "$model")
  fi

  if [[ "$dry_run" == "1" ]]; then
    printf 'Running Fig. 11(%s) command:' "$case_name"
    printf ' %q' "${command[@]}"
    printf '\n'
    continue
  fi

  echo "Running Fig. 11($case_name) with $model"
  "${command[@]}"
  run_status=$?

  echo "Cooling down for $cooldown_seconds seconds"
  sleep "$cooldown_seconds"
  check_workdir || exit 1

  if [[ "$run_status" -ne 0 ]]; then
    echo "Fig. 11($case_name) failed with exit code $run_status" >&2
    exit "$run_status"
  fi
  normalize_run_metadata "$output_dir"
  python3 "$project_root/examples/fig11/calculate_rate.py" \
    --sender_log "$output_dir/sender.log" \
    --trace "$trace" \
    --duration "$duration" \
    --output "$output_dir/rate.pdf"
done

if [[ "$dry_run" == "1" ]]; then
  echo "All Fig. 11 commands printed; no calls were run"
else
  echo "All Fig. 11 example runs completed successfully"
fi