# Benchmark Network Traces

This directory contains the fixed benchmark suite of 120 network traces from the FCC wired, mmWave 5G, and Norway 3G datasets.

## Distribution

| Dataset | Category | Traces |
| --- | --- | ---: |
| FCC wired | HIGH_DYNAMIC | 6 |
| FCC wired | HIGH_STABLE | 7 |
| FCC wired | LOW_DYNAMIC | 6 |
| FCC wired | LOW_STABLE | 7 |
| FCC wired | MID_DYNAMIC | 7 |
| FCC wired | MID_STABLE | 7 |
| FCC wired | MIXED_DYNAMIC | 7 |
| FCC wired | MIXED_STABLE | 7 |
| mmWave 5G | HIGH_DYNAMIC | 9 |
| mmWave 5G | LOW_DYNAMIC | 3 |
| mmWave 5G | MIXED_DYNAMIC | 8 |
| Norway 3G | HIGH_DYNAMIC | 7 |
| Norway 3G | MID_DYNAMIC | 7 |
| Norway 3G | MID_STABLE | 6 |
| Norway 3G | MID_UNKNOWN | 7 |
| Norway 3G | MIXED_DYNAMIC | 7 |
| Norway 3G | MIXED_STABLE | 6 |
| Norway 3G | MIXED_UNKNOWN | 6 |
| **Total** | **18 classes** | **120** |

## Layout

```text
traces/
|-- fcc_wried/
|-- mmwave_5g/
|-- norway_3g/
`-- README.md
```

For benchmark reporting, first average results within each of the 18 classes, then report the macro-average across classes. This prevents differences in class sample counts from affecting class weights.
