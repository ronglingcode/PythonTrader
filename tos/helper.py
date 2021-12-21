from datetime import datetime
import pandas as pd

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
    df['vwap'] = (((df['High'] + df['Low'])/2)*df['Volume']).cumsum() / df['Volume'].cumsum()

def add_or_update_data_frame(df, time_sales_data):
    if has_row_in_data_frame(df, key):
        update_data_frame(df, time_sales_data)
    else
        add_data_frame(df, time_sales_data)


def has_row_in_data_frame(df, key) -> bool:
    # https://pandas.pydata.org/pandas-docs/stable/user_guide/indexing.html
    try:
        df.loc()
    except KeyError:
        return False

def add_data_frame(df, time_sales_data):
    df2 = {'Name': 'Amy', 'Maths': 89, 'Science': 93}
    df = df.append(df2)

def update_data_frame(df, time_sales_data):
    df.loc[row index,['column-names']] = value
