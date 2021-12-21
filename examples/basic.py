import yfinance as yf
import mplfinance as mpf

ticker = 'AAPL'
start = '2021-12-16'
interval = '5m'
data = yf.download(tickers=ticker, start=start, period='1d', interval=interval)
print(data)

col = mpf.make_marketcolors(up='#2E7D32',down='#D32F2F',inherit=True)
sty = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=col)

kwargs = dict(type='candle', volume=True, style=sty)
mpf.plot(data, **kwargs)