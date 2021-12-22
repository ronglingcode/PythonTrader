from datetime import datetime, timedelta
from pytz import timezone
import yfinance as yf

def get_price_history_for_day_trading(symbol: str):
    now = datetime.now(timezone('US/Pacific'))
    start = "{y}-{m}-{d}".format(
        y=now.year, m=now.month, d=now.day
    )

    df = yf.download(tickers=symbol, start=start, period='1d', interval='1m', prepost=True)
    
    cutoff = now - timedelta(minutes=20)
    df = df.truncate(before=cutoff)
    return df
