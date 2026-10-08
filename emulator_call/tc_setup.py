"""Apply network trace entries with Linux tc."""

import argparse
import json
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


INTERFACE = "lo"
is_first_run = True


def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def remove_network_config():
    subprocess.run(
        f"sudo tc qdisc del dev {INTERFACE} root",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def apply_network_config(config):
    global is_first_run

    duration_ms = config.get("duration", 60000)
    capacity = config.get("capacity", 1000) / 1000
    loss = config.get("loss", 0)
    rtt = config.get("rtt", 0) / 2
    jitter = config.get("jitter", 0)

    print(
        f"{current_time()} - Applying: capacity={capacity}Mbit, "
        f"loss={loss}%, rtt={rtt}ms, jitter={jitter}ms for {duration_ms}ms"
    )

    if is_first_run:
        delete_command = f"sudo tc qdisc del dev {INTERFACE} root"
        print(f"{current_time()} - Executing: {delete_command}")
        subprocess.run(delete_command, shell=True)

    action = "add" if is_first_run else "change"
    netem_command = (
        f"sudo tc qdisc {action} dev {INTERFACE} root netem "
        f"rate {capacity}Mbit"
    )
    is_first_run = False

    if rtt > 0:
        netem_command += f" delay {rtt}ms"
        if jitter > 0:
            netem_command += f" {jitter}ms distribution normal"

    if loss > 0:
        netem_command += f" loss {loss}%"

    netem_command += " limit 50"

    print(f"{current_time()} - Executing: {netem_command}")
    result = subprocess.run(netem_command, shell=True)
    if result.returncode != 0:
        print(f"{current_time()} - 'change' failed, trying 'add'")
        netem_command = netem_command.replace("change", "add", 1)
        print(f"{current_time()} - Executing: {netem_command}")
        result = subprocess.run(netem_command, shell=True)

    if result.returncode != 0:
        raise RuntimeError("Failed to apply network configuration")


def main():
    parser = argparse.ArgumentParser(
        description="Apply network configuration from a JSON file."
    )
    parser.add_argument(
        "--config", required=True, help="Path to the JSON configuration file"
    )
    parser.add_argument(
        "--ready-file", help="Write this file after the first qdisc is applied"
    )
    args = parser.parse_args()

    with open(args.config, "r") as config_file:
        config_data = json.load(config_file)

    trace_patterns = config_data.get("uplink", {}).get("trace_pattern", [])
    if not trace_patterns:
        raise ValueError("uplink.trace_pattern is empty")

    signal.signal(signal.SIGTERM, lambda _signum, _frame: sys.exit(0))
    deadline_ns = time.monotonic_ns()
    ready = False

    try:
        while True:
            for config in trace_patterns:
                duration_ms = config.get("duration", 60000)
                if duration_ms <= 0:
                    raise ValueError(
                        f"Trace duration must be positive: {duration_ms}"
                    )

                command_start_ns = time.monotonic_ns()
                apply_network_config(config)
                command_elapsed_ms = (
                    time.monotonic_ns() - command_start_ns
                ) / 1_000_000

                if not ready:
                    if args.ready_file:
                        Path(args.ready_file).write_text(
                            f"{time.monotonic_ns()}\n"
                        )
                    ready = True

                deadline_ns += int(duration_ms * 1_000_000)
                remaining_ns = deadline_ns - time.monotonic_ns()
                if remaining_ns > 0:
                    time.sleep(remaining_ns / 1_000_000_000)
                else:
                    delay_ms = -remaining_ns / 1_000_000
                    print(
                        f"{current_time()} - Trace is "
                        f"{delay_ms:.3f}ms behind schedule"
                    )

                print(
                    f"{current_time()} - tc command took "
                    f"{command_elapsed_ms:.3f}ms"
                )
    finally:
        remove_network_config()


if __name__ == "__main__":
    main()