import json
import os
import re

import matplotlib.pyplot as plt
import numpy as np

BWE_REX_FORMAT=r"\(rtp_transport_controller_send\.cc:\d+\): PostUpdates SetTargetRate: (\d+).*?PostUpdates SetTargetRate Time: (\d+)"
SEND_REX_FORMAT=r"\(rtp_sender_egress\.cc:\d+\): RtpSenderEgress::SendPacket: packet ssrc: (\d+), sequence number: (\d+), timestamp: \d+, payload type: (\d+), payload size: (\d+), packet_sendtime: (\d+) ms, packet_type:*"

class Iterator:
    def __init__(self, line):
        bwe_regex = re.search(BWE_REX_FORMAT, line)
        if bwe_regex:
            self.bwe = int(bwe_regex.group(1))
            self.timestamp = int(bwe_regex.group(2))
        self.reset()

    def reset(self):
        self.audio = 0
        self.video = 0
        self.rtx = 0

    def add_send(self, line):
        pkt_regex = re.search(SEND_REX_FORMAT, line)
        if pkt_regex:            
            payload_type = int(pkt_regex.group(3))
            # print("Payload type:", payload_type, "Payload size:", pkt_regex.group(4))
            if payload_type == 111:
                self.audio += int(pkt_regex.group(4))
            elif payload_type == 125:
                self.video += int(pkt_regex.group(4))
            elif payload_type == 122:
                print("RTX packet detected, payload size:", pkt_regex.group(3))
                self.rtx += int(pkt_regex.group(4))
    
    def calculate(self, end_time):

        duration = end_time - self.timestamp
        assert duration > 0

        return {
            "timestamp": self.timestamp,
            "bwe": self.bwe / 1000 ,  # Convert to Mbps
            "audio_rate": self.audio * 8 / duration,
            "video_rate": (self.audio + self.video) * 8 / duration,
            "rtx_rate": (self.audio + self.video + self.rtx) * 8 / duration
        }
        
class RateCalculator:
    def __init__(self, args):
        self.sender_log = args.sender_log
        self.trace = args.trace
        self.output = args.output or self.sender_log.replace('.log', '.pdf')
        self.reset()

    def reset(self):
        self.data = []

    def parse_sender_log(self):
        for line in open(self.sender_log):
            if "PostUpdates SetTargetRate: " in line:
                new_iterator = Iterator(line)
                if len(self.data) == 0 or self.data[-1].timestamp + 100 < new_iterator.timestamp:
                    # print(new_iterator.timestamp)
                    self.data.append(Iterator(line))
                continue
            if "RtpSenderEgress::SendPacket" in line: 
                self.data[-1].add_send(line)
                continue

    def load_capacity(self):
        with open(self.trace, encoding="utf-8") as trace_file:
            pattern = json.load(trace_file)["uplink"]["trace_pattern"]
        timestamps = [float(row["time"]) for row in pattern]
        capacities = [int(row["capacity"]) / 1000 for row in pattern]
        return timestamps, capacities

    def calculate_rates(self):
        self.parse_sender_log()
        results = {
            "audio_rate": [],
            "video_rate": [],
            "rtx_rate": [],
            "bwe": [],
            "timestamp": []
        }
        for i in range(len(self.data) - 1):
            result = self.data[i].calculate(self.data[i + 1].timestamp)
            results["audio_rate"].append(result["audio_rate"] / 1000)  # Convert to Mbps
            results["video_rate"].append(result["video_rate"] / 1000)  # Convert to Mbps
            results["rtx_rate"].append(result["rtx_rate"] / 1000)  # Convert to Mbps
            results["bwe"].append(result["bwe"] / 1000)  # Convert to Mbps
            results["timestamp"].append(result["timestamp"])

        start_time = self.data[0].timestamp
        for i in range(len(results["timestamp"])):
            results["timestamp"][i] -= start_time         
            results["timestamp"][i] /= 1000
            results["timestamp"][i] -= 20

        results["smooth_video_rate"] = []
        results["smooth_rtx_rate"] = []
        for i in range(len(results["video_rate"])):
            results["smooth_video_rate"].append(np.mean(results["video_rate"][max(0, i-5):min(len(results["video_rate"]), i+5)]))
            results["smooth_rtx_rate"].append(np.mean(results["rtx_rate"][max(0, i-5):min(len(results["rtx_rate"]), i+5)]))
        print(results['bwe'][-1])
        capacity_times, capacities = self.load_capacity()
        plt.figure(figsize=(2.5, 2))
        plt.step(
            capacity_times,
            capacities,
            where="post",
            linestyle="--",
            color="black",
            label="Network Capacity",
        )
        # plt.plot(results["timestamp"], results["audio_rate"], color='blue')
        # plt.fill_between(results["timestamp"], 0, results["audio_rate"], color='blue', alpha=0.5, label='Audio Rate')
        plt.plot(results["timestamp"], results["video_rate"], color='green')
        plt.fill_between(results["timestamp"], 0, results["video_rate"], color='green', alpha=0.5, label='New Media')
        plt.plot(results["timestamp"], results["rtx_rate"], color='orange')
        plt.fill_between(results["timestamp"], results["video_rate"], results["rtx_rate"], color='orange', alpha=0.5, label='Retransmission')
        plt.xlabel('Time (s)')
        plt.ylabel('Rate (Mbps)')
        
        plt.plot(results["timestamp"], results["bwe"], "-", color='red', label="BWE")
        
        # plt.yscale("log", base=2)
        plt.ylim(0, 6)
        plt.xlim(0, 40)
        # plt.yticks([16, 64, 256, 1024, 4096], ['16K', '64K', '256K', '1M', '4M'])
        plt.legend(loc='upper left', fontsize=8)
        plt.grid()
        plt.tight_layout()
        print(self.output)
        plt.savefig(self.output)
        plt.close()




if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Calculate sending rates from sender log.')
    parser.add_argument('--sender_log', type=str, required=True, help='Path to the sender log file.')
    parser.add_argument('--trace', type=str, required=True, help='Path to the network trace JSON file.')
    parser.add_argument('--duration', type=float, default=60, help='Plot duration in seconds.')
    parser.add_argument('--output', type=str, help='Output plot path (default: sender PDF).')
    args = parser.parse_args()

    if not os.path.exists(args.sender_log):
        print(f"Sender log {args.sender_log} does not exist, exiting.")
        exit(1)
    if not os.path.exists(args.trace):
        print(f"Trace {args.trace} does not exist, exiting.")
        exit(1)
    print(f"Processing sender log: {args.sender_log}")
    calculator = RateCalculator(args)
    calculator.calculate_rates()

    # for i in range(31, 51):
    #     sender_log = f"/home/onl/paper/sending_size/education_1080p_30fps/1G/run_{i}/sender.log"
    #     if not os.path.exists(sender_log):
    #         print(f"Sender log {sender_log} does not exist, skipping.")
    #         continue

    #     print(f"Processing sender log: {sender_log}")
    #     args = type('', (), {})()
    #     args.sender_log = sender_log
    #     calculator = RateCalculator(args)
    #     calculator.calculate_rates()
