from datetime import datetime, timedelta
import pandas as pd
from helpers.datetime_helper import round_to_one_minute
from data_models.streaming_timesales_content import StreamingTimeSaleContent

def datetime_to_tos_timestamp(dt: datetime) -> int:
    f = datetime.timestamp(dt) * 1000
    return (int)(f)

def convert_price_history_to_data_frame(json_data):
    candles = json_data['candles']
    data = {
        'Date': [],
        'Open': [],
        'High': [],
        'Low': [],
        'Close': [],
        'Volume': [],
    }
    for c in candles:
        d = datetime.fromtimestamp(c['datetime']/1000)
        data['Date'].append(d)
        data['Open'].append(c['open'])
        data['High'].append(c['high'])
        data['Low'].append(c['low'])
        data['Close'].append(c['close'])
        data['Volume'].append(c['volume'])

    df = pd.DataFrame(data)
    df.set_index('Date', inplace=True)
    #df['vwap'] = (((df['High'] + df['Low'])/2)*df['Volume']).cumsum() / df['Volume'].cumsum()
    return df

def generate_sample_price_history():
    json_data = {'candles': []}
    current_minute = datetime.now()
    current_minute = round_to_one_minute(current_minute)
    previous_minute = current_minute - timedelta(minutes=1)

    json_data['candles'].append({
        'datetime': previous_minute.timestamp()*1000,
        'open': 4636,
        'high': 4640,
        'low': 4630,
        'close': 4638,
        'volume': 100,
    })
    json_data['candles'].append({
        'datetime': current_minute.timestamp()*1000,
        'open': 4637,
        'high': 4641,
        'low': 4630,
        'close': 4638,
        'volume': 155,
    })
    return convert_price_history_to_data_frame(json_data)

def add_or_update_data_frame(df, timesale: StreamingTimeSaleContent):
    if has_row_in_data_frame(df, timesale.one_minute_bucket_time):
        update_data_frame(df, timesale)
    else:
        add_data_frame2(df, timesale)

def has_row_in_data_frame(df, dt: datetime) -> bool:
    # https://pandas.pydata.org/pandas-docs/stable/user_guide/indexing.html
    try:
        df.loc[dt]
        return True
    except KeyError:
        return False


def add_data_frame2(df, timesale: StreamingTimeSaleContent):
    bucket = timesale.one_minute_bucket_time
    df.loc[bucket] = [
        timesale.last_price,
        timesale.last_price,
        timesale.last_price,
        timesale.last_price,
        timesale.last_size,
    ]

def add_data_frame(df, timesale: StreamingTimeSaleContent):
    timestamp = timesale.one_minute_bucket_time.timestamp()
    json_data = {'candles': []}

    json_data['candles'].append({
        'datetime': timestamp*1000,
        'open': timesale.last_price,
        'high': timesale.last_price,
        'low': timesale.last_price,
        'close': timesale.last_price,
        'volume': timesale.last_size,
    })
    df2 = convert_price_history_to_data_frame(json_data)
    df = df.append(df2)
    print(df)

def update_data_frame(df, timesale: StreamingTimeSaleContent):
    last_price = timesale.last_price
    bucket = timesale.one_minute_bucket_time
    if last_price > df.loc[bucket, 'High']:
        df.loc[bucket, 'High'] = last_price
    elif last_price < df.loc[bucket, 'Low']:
        df.loc[bucket, 'Low'] = last_price
    df.loc[bucket, 'Close'] = last_price
    df.loc[bucket, 'Volume'] = df.loc[bucket, 'Volume'] + timesale.last_size