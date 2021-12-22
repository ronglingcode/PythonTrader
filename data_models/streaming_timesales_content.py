from datetime import datetime
from helpers.datetime_helper import round_to_one_minute
class StreamingTimeSaleContent:
    def load_from_tos(self, content: dict):
        self.symbol = content["key"]
        if "1" in content:
            self.trade_time = datetime.fromtimestamp(content['1']/1000)
            self.one_minute_bucket_time = round_to_one_minute(self.trade_time)
        if "2" in content:
            self.last_price = content["2"]
        if "3" in content:
            self.last_size = content["3"]
        if "4" in content:
            self.last_sequence = content["4"]
            self.received_time = datetime.now()
    