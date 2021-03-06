from tos.client import TDClient
import time
from threading import Thread
import asyncio
import pandas as pd

stock_data = []
TDSession = TDClient(
    credentials_path="C:\\AutoTrading\\tdameritrade_settings.json"
)
def start_streaming():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Create a new session, credentials path is required.
    TDSession = TDClient(
        credentials_path="C:\\AutoTrading\\tdameritrade_settings.json"
    )
    client = TDSession.create_streaming_session()
    client.timesale(
        service='TIMESALE_FUTURES',
        symbols=['/ES'],
        fields=[0, 1, 2, 3, 4]
    )
    client.stream(stock_data)

df = TDSession.get_price_history_for_day_trading('SPY')

thread = Thread(target=start_streaming)
thread.start()
# start_streaming()


"""

def on_message(wsapp, message):
    print(message)

wsapp = websocket.WebSocketApp("",on_message=on_message)
wsapp.run_forever()


# Login to the session
TDSession.login()


# Create a streaming sesion
TDStreamingClient = TDSession.create_streaming_session()
TDStreamingClient.write_behavior(
    file_path = "raw_data.csv",
    append_mode = True
)
TDStreamingClient.timesale(service='TIMESALE_FUTURES', symbols=['/ES'], fields=[0, 1, 2, 3, 4])
"""