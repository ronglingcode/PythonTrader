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

color = mpf.make_marketcolors(up='#3A7153',down='#AC2E2E',inherit=True)
style = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=color)
kwargs = dict(type='candle', volume=True, style=style)
fig, axlist = mpf.plot(df, returnfig=True, **kwargs)

def onclick(event):
    print('%s click: button=%d, x=%d, y=%d, xdata=%f, ydata=%f' %
          ('double' if event.dblclick else 'single', event.button,
           event.x, event.y, event.xdata, event.ydata))

def onKeyPress(event):
    print(event.__dict__)
def onKeyRelease(event):
    print(event)

def onMouseMove(event):
    print(event.__dict__)

cid1 = fig.canvas.mpl_connect('button_press_event', onclick)
cid2 = fig.canvas.mpl_connect('key_press_event', onKeyPress)
cid3 = fig.canvas.mpl_connect('key_release_event', onKeyRelease)


ax1 = axlist[0] # price
ax2 = axlist[2] # volume
def animate(i):
    ax1.clear()
    ax2.clear()
    kwargs2 = dict(type='candle', style=style)
    partial_df = df.iloc[-20:]
    mpf.plot(partial_df,ax=ax1, volume=ax2, **kwargs2)

ani = animation.FuncAnimation(fig, animate, interval=100)
mpf.show()
