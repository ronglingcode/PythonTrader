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

fig = mpf.figure(figsize=(12,9))
#fig, axlist = mpf.plot(df, returnfig=True, **kwargs)
ax_stock_1_price = fig.add_subplot(2,2,1,style='blueskies')
ax_stock_2_price = fig.add_subplot(2,2,2,style='yahoo')
ax_stock_1_volume = fig.add_subplot(2,2,3,style='blueskies')
ax_stock_2_volume = fig.add_subplot(2,2,4,style='yahoo')
s   = mpf.make_mpf_style(base_mpl_style='fast',base_mpf_style='nightclouds')

mpf.plot(partial_df,ax=ax_stock_1_price, volume=ax_stock_1_volume, axtitle='blueskies')
mpf.plot(partial_df,type='candle',ax=ax_stock_2_price, volume=ax_stock_2_volume,axtitle='yahoo')


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
    partial_df = df.iloc[-60:]
    mpf.plot(partial_df,ax=ax_stock_1_price, volume=ax_stock_1_volume,axtitle='blueskies',xrotation=15)
    #mpf.plot(partial_df,ax=ax1, volume=ax2, **kwargs2)

ani = animation.FuncAnimation(fig, animate, interval=50)

mpf.show()
