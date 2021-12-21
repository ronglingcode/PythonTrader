import yfinance as yf
import mplfinance as mpf

ticker = 'SPY'
start = '2021-12-19'
interval = '5m'
data = yf.download(tickers=ticker, start=start, period='1d', interval=interval, prepost=True)
print(data)

col = mpf.make_marketcolors(up='#2E7D32',down='#D32F2F',inherit=True)
sty = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=col)

kwargs = dict(type='candle', volume=True, style=sty)
mpf.plot(data, **kwargs)
