class Estimator(object):
    def __init__(self):
        self.last_bwe = 300_000

    def report_states(self, stats: dict):
            '''
            stats is a dict with the following items
            {
                "send_time_ms": uint,
                "arrival_time_ms": uint,
                "payload_type": int,
                "sequence_number": uint,
                "ssrc": int,
                "padding_length": uint,
                "header_length": uint,
                "payload_size": uint
            }
            '''

    def get_estimated_bandwidth(self):
        return self.last_bwe