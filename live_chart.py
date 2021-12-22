from tos.client import TDClient
from datetime import date, datetime
from datetime import timedelta
import mplfinance as mpf
import pandas as pd
from tos.helper import generate_sample_price_history
import asyncio
from threading import Thread
import matplotlib.animation as animation

TDSession = TDClient(
    credentials_path="C:\\AutoTrading\\tdameritrade_settings.json"
)
#df = TDSession.get_price_history_for_day_trading('SPY')
df = generate_sample_price_history()
print(df)

def start_streaming():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TDSession.create_streaming_session()
    client.timesale(
        service='TIMESALE_FUTURES',
        symbols=['/ES'],
        fields=[0, 1, 2, 3, 4]
    )
    client.stream(df)


thread = Thread(target=start_streaming)
thread.start()

color = mpf.make_marketcolors(up='#2E7D32',down='#D32F2F',inherit=True)
style = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=color)
kwargs = dict(type='candle', volume=True, style=style)
fig, axlist = mpf.plot(df, returnfig=True, **kwargs)
ax1 = axlist[0] # price
ax2 = axlist[2] # volume
def animate(i):
    ax1.clear()
    ax2.clear()
    kwargs2 = dict(type='candle', style=style)
    mpf.plot(df,ax=ax1, volume=ax2, **kwargs2)

ani = animation.FuncAnimation(fig, animate, interval=100)
mpf.show()
