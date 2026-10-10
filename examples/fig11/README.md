# Fig. 11 Example Outputs

This directory archives the three 60-second Screen-sharing runs used in Fig. 11.

| Panel | Estimator | Network condition |
| --- | --- | --- |
| `a/` | Default fixed 2 Mbit/s BWE | Effectively unconstrained capacity with random loss |
| `b/` | GCC | Fixed 2 Mbit/s capacity with random loss |
| `c/` | Gemini | Fixed 2 Mbit/s capacity with random loss |

The selected traces reproduce these conditions. Each result directory includes `run.json`, telemetry, sender and receiver logs, any non-empty process logs, and `rate.pdf`. The plot shows the trace capacity, BWE, new-media rate, and retransmission rate. QoE is not calculated for this reproduction.

Run all three cases from any directory:

```bash
./examples/fig11/run_fig11_random_loss.sh
```

New results are written to `a/`, `b/`, and `c/` under `results/example-runs/fig11-random-loss/`; the archived outputs in this directory are not overwritten. Set `DRY_RUN=1` to print all three emulator commands without running them.
