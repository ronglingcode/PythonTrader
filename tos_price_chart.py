from tos.client import TDClient
from datetime import date, datetime
from datetime import timedelta
import mplfinance as mpf
import pandas as pd
from helpers.yahoo import get_price_history_for_day_trading

TDSession = TDClient(
    credentials_path="C:\\AutoTrading\\tdameritrade_settings.json"
)

df = get_price_history_for_day_trading('ES=F')

col = mpf.make_marketcolors(up='#2E7D32',down='#D32F2F',inherit=True)
sty = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=col)

kwargs = dict(type='candle', volume=True, style=sty)
mpf.plot(df, **kwargs)
