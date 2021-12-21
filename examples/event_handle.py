import yfinance as yf
import mplfinance as mpf
from matplotlib import pyplot as plt

# remove shortcut keys
# https://matplotlib.org/stable/api/matplotlib_configuration_api.html#matplotlib.rcParams
plt.rcParams['keymap.save'].remove('s')
plt.rcParams['keymap.fullscreen'].remove('f')
ticker = 'AAPL'
start = '2021-12-16'
interval = '15m'
data = yf.download(tickers=ticker, start=start, period='1d', interval=interval)
print(data)

col = mpf.make_marketcolors(up='#2E7D32',down='#D32F2F',inherit=True)
sty = mpf.make_mpf_style(base_mpf_style='charles', marketcolors=col)

kwargs = dict(type='candle', volume=True, style=sty, returnfig=True)
fig, ax = mpf.plot(data, **kwargs)


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
# cid4 = fig.canvas.mpl_connect('motion_notify_event', onMouseMove)
# https://matplotlib.org/stable/users/explain/event_handling.html

mpf.show()
