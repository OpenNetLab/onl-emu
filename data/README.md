# Dataset

This directory contains the media and network data used to construct the trace-driven benchmark described in the paper. The dataset is designed for evaluating bandwidth-estimation (BWE) algorithms for real-time communication (RTC) across diverse media workloads and network conditions.

The source pool contains 500 curated media links in five RTC-relevant categories and network measurements from three public datasets, supplemented with measurements collected on our real-node testbed. From this pool, the released benchmark fixes five representative media sources and 120 network cases, producing a reproducible \(5 \times 120 = 600\)-case evaluation grid. The fixed benchmark is available under [`benchmark/`](../benchmark/).

## Directory structure

### `media/`

[`media/`](media/) contains lists of YouTube video URLs grouped into five workload categories:

| Category | Representative RTC workload | BWE-relevant characteristics |
| --- | --- | --- |
| `screen_sharing` | Conferencing and remote collaboration | Long low-motion intervals followed by bursts at slide or window changes |
| `talking_head` | Video conferencing | Relatively stable traffic with localized facial and upper-body motion |
| `room_camera` | Multi-party conferencing | Multiple motion regions and occasional camera or speaker changes |
| `mobile_camera` | Mobile live streaming | Sustained camera motion, scene changes, and bitrate spikes |
| `gameplay` | Cloud gaming | Rapid view changes, frequent motion bursts, and latency-sensitive adaptation |

The videos were manually curated from content published under YouTube's Creative Commons license at the time of collection. This repository stores URLs only and does not redistribute the video files. The YouTube UGC Dataset paper [1] motivates the use of YouTube as a diverse source of user-generated content; the URL lists in this repository are our own RTC-oriented selection, not a redistribution of that dataset.

Licenses and availability on external platforms may change. Before downloading, modifying, or redistributing a video, users must verify its current license and comply with the applicable attribution and platform requirements.

### `traces/`

[`traces/`](traces/) contains network measurements normalized for the trace-driven simulator and emulator:

| Directory | Original source | What the source measures |
| --- | --- | --- |
| [`fcc_wried/`](traces/fcc_wried/) | [FCC Measuring Broadband America](https://www.fcc.gov/reports-research/reports/measuring-broadband-america) [2] | Fixed-broadband throughput and RTT measurements. The directory name is retained for compatibility despite the `wried` typo. |
| [`norway_3g/`](traces/norway_3g/) | [Norway 3G/HSDPA commute-path traces](http://skuld.cs.umass.edu/traces/mmsys/2013/pathbandwidth/) [3] | Mobile bandwidth measurements collected on public-transport and driving routes in Norway. |
| [`mmwave_5g/`](traces/mmwave_5g/) | [Commercial 5G mmWave uplink dataset](https://github.com/NUWiNS/sigcomm-5gmemu-5g-mmWave-uplink-data) [4] | Uplink throughput and latency measurements under static, walking, and driving scenarios on 5G and LTE networks in the United States. |
| [`random_loss/`](traces/random_loss/) | Our real-node testbed | Processed measurements used to represent non-congestion random-loss conditions. This is derived project data, not a fourth independent public dataset. |

Each normalized trace describes time-varying **duration**, **capacity**, **one-way delay**, and **packet loss**. Because the public datasets expose different subsets of these fields, the missing values are completed as described in the paper:

- **FCC:** one-way delay is half of the reported RTT; loss is set to zero for the fixed-broadband traces.
- **Norway 3G:** capacity comes from the published bandwidth logs; delay is set to a constant representative HSDPA delay, and loss is assigned from matching cellular measurements on our real-node testbed.
- **5G mmWave:** capacity and the provided delay time series are retained; loss is assigned from matching 5G measurements on our real-node testbed.
- **Random loss:** traces are derived from real-node measurements and processed to isolate random-loss behavior.

Each entry in `uplink.trace_pattern` uses the following units:

| Field | Unit | Meaning |
| --- | --- | --- |
| `duration` | milliseconds | Time for which the entry is applied |
| `capacity` | Kbit/s | Uplink capacity |
| `loss` | percent | Packet-loss percentage, where `1` means 1% |
| `rtt` | milliseconds | Round-trip time; the emulator applies half as one-way delay |
| `time` | seconds | Entry start time relative to the beginning of the trace |

The original source identifier is preserved in the JSON `from` field whenever available, so a normalized trace can be mapped back to its upstream record. Normalized values and derived fields should not be interpreted as unmodified raw measurements from the upstream datasets.

## From source pool to benchmark

The public and testbed traces form a source pool rather than the benchmark itself. As described in the paper, we replay media--trace pairs, analyze their network and QoE characteristics, down-sample redundant normal cases, and retain more underrepresented tail conditions such as abrupt capacity changes, high or variable delay, and random loss. This process produces the 120 released network cases.

For media, the default benchmark uses stratified random sampling to select one video from each of the five categories. The resulting five-video suite is then fixed across all evaluated models. Different media samples can change absolute QoE values and close pairwise rankings; the larger source pool is provided for broader robustness studies.

## Licensing and attribution

The public datasets remain subject to their respective upstream licenses and terms. Please cite the original dataset publication when using a corresponding source, and cite our paper when using the normalized traces, derived testbed data, or released benchmark construction.

## References

1. Y. Wang, S. Inguva, and B. Adsumilli, "YouTube UGC Dataset for Video Compression Research," *IEEE MMSP*, 2019. [doi:10.1109/MMSP.2019.8901772](https://doi.org/10.1109/MMSP.2019.8901772)
2. Federal Communications Commission, "Measuring Broadband America." [Program and data portal](https://www.fcc.gov/reports-research/reports/measuring-broadband-america)
3. H. Riiser, P. Vigmostad, C. Griwodz, and P. Halvorsen, "Commute Path Bandwidth Traces from 3G Networks: Analysis and Applications," *ACM MMSys*, 2013. [Dataset](http://skuld.cs.umass.edu/traces/mmsys/2013/pathbandwidth/)
4. M. Ghoshal et al., "An In-Depth Study of Uplink Performance of 5G mmWave Networks," *ACM SIGCOMM 5G-MeMU*, 2022. [Dataset and citation](https://github.com/NUWiNS/sigcomm-5gmemu-5g-mmWave-uplink-data)
