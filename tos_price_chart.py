from tos.client import TDClient
from datetime import date, datetime
from datetime import timedelta
import mplfinance as mpf
import pandas as pd

TDSession = TDClient(
    credentials_path="C:\\AutoTrading\\tdameritrade_settings.json"
)

# Make the request
# Define today.
datetime_now = datetime.now()

# Define 300 days ago.
today_ago = datetime.now() - timedelta(days=1)
datetime_now = str(int(round(datetime_now.timestamp() * 1000)))
today_ago = str(int(round(today_ago.timestamp() * 1000)))

# These values will now be our startDate and endDate parameters.
hist_startDate = today_ago
hist_endDate = datetime_now

response = TDSession.get_price_history_for_day_trading(
    symbol='SPY',
)
candles = response['candles']

data = {
    'Date': [],
    'Open': [],
    'High': [],
    'Low': [],
    'Close': [],
    'Volume': [],
}
cutoff = datetime(2021,12,20,22)
for c in candles:
    d = datetime.fromtimestamp(c['datetime']/1000)
    if d < cutoff:
        continue
    print(d)
    data['Date'].append(d)
    data['Open'].append(c['open'])
    data['High'].append(c['high'])
    data['Low'].append(c['low'])
    data['Close'].append(c['close'])
    data['Volume'].append(c['volume'])

df = pd.DataFrame(data)
df.set_index('Date', inplace=True)
df['vwap'] = (((df['High'] + df['Low'])/2)*df['Volume']).cumsum() / df['Volume'].cumsum()
add = mpf.make_addplot(df['vwap'])
col = mpf.make_marketcolors(up='#2E7D32',down='#D32F2F',inherit=True)
sty = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=col)

kwargs = dict(type='candle', volume=True, style=sty, addplot=add)
mpf.plot(df, **kwargs)
