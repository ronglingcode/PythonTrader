from tos.client import TDClient
from datetime import date, datetime
from datetime import timedelta
import mplfinance as mpf
import pandas as pd
from tos.helper import generate_sample_price_history
import asyncio
from threading import Thread
import matplotlib.animation as animation
from matplotlib import pyplot as plt
plt.rcParams['keymap.save'].remove('s')
plt.rcParams['keymap.fullscreen'].remove('f')

symbol = 'SPY'
TDSession = TDClient(
    credentials_path="C:\\AutoTrading\\tdameritrade_settings.json"
)
df = TDSession.get_price_history_for_day_trading(symbol)

def start_streaming():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TDSession.create_streaming_session()
    """client.timesale(
        service='TIMESALE_FUTURES',
        symbols=['/ES'],
        fields=[0, 1, 2, 3, 4]
    )
    """
    client.timesale(service='TIMESALE_EQUITY', symbols=[symbol], fields=[0, 1, 2, 3, 4])
    client.stream(df)


thread = Thread(target=start_streaming)
thread.start()

color = mpf.make_marketcolors(up='#3A7153',down='#AC2E2E',inherit=True)
style = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=color)
kwargs = dict(type='candle', volume=True, style=style)
partial_df = df.iloc[-60:]

fig = mpf.figure(figsize=(12,9), style='yahoo')

gs = fig.add_gridspec(4, 2)

#fig, axlist = mpf.plot(df, returnfig=True, **kwargs)
# gs = fig.add_gridspec(nrows, ncols)
# ax = fig.add_subplot(gs[row:row+rowspan, col:col+colspan])
ax_stock_1_price = fig.add_subplot(gs[0:3, 0:1])
ax_stock_2_price = fig.add_subplot(gs[0:3, 1:2])
ax_stock_1_volume = fig.add_subplot(gs[3:4, 0:1])
ax_stock_2_volume = fig.add_subplot(gs[3:4,1:2])

mpf.plot(partial_df,type='candle',ax=ax_stock_1_price, volume=ax_stock_1_volume, axtitle='blueskies', tight_layout=True)
mpf.plot(partial_df,type='candle',ax=ax_stock_2_price, volume=ax_stock_2_volume,axtitle='yahoo', tight_layout=True)
fig.tight_layout()

def onclick(event):
    print(event.__dict__)

def onKeyPress(event):
    print(event.__dict__)
def onKeyRelease(event):
    print(event)

def onMouseMove(event):
    print(event.__dict__)

cid1 = fig.canvas.mpl_connect('button_press_event', onclick)
cid2 = fig.canvas.mpl_connect('key_press_event', onKeyPress)
cid3 = fig.canvas.mpl_connect('key_release_event', onKeyRelease)

def animate(i):
    ax_stock_1_price.clear()
    ax_stock_1_volume.clear()
    ax_stock_2_price.clear()
    ax_stock_2_volume.clear()
    partial_df = df.iloc[-60:]
    mpf.plot(partial_df,type='candle',ax=ax_stock_1_price, volume=ax_stock_1_volume,axtitle='blueskies')
    mpf.plot(partial_df,type='candle',ax=ax_stock_2_price, volume=ax_stock_2_volume,axtitle='yahoo')
    #mpf.plot(partial_df,ax=ax1, volume=ax2, **kwargs2)

ani = animation.FuncAnimation(fig, animate, interval=1000)

mpf.show()
