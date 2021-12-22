import matplotlib.pyplot as plt
import numpy as np
import math


import yfinance as yf
import mplfinance as mpf

ticker = 'SPY'
start = '2021-12-19'
interval = '5m'
df = yf.download(tickers=ticker, start=start, period='1d', interval=interval, prepost=True)


fig = mpf.figure(figsize=(12,9))
ax1 = fig.add_subplot(2,2,1,style='blueskies')
ax2 = fig.add_subplot(2,2,2,style='yahoo')

s   = mpf.make_mpf_style(base_mpl_style='fast',base_mpf_style='nightclouds')
ax3 = fig.add_subplot(2,2,3,style=s)

ax4 = fig.add_subplot(2,2,4,style='starsandstripes')
mpf.plot(df,ax=ax1,axtitle='blueskies',xrotation=15)
mpf.plot(df,type='candle',ax=ax2,axtitle='yahoo',xrotation=15)
mpf.plot(df,ax=ax3,type='candle',axtitle='nightclouds')
mpf.plot(df,type='candle',ax=ax4,axtitle='starsandstripes')


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

# Combine all the operations and display
plt.show()