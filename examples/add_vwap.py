df = get_price_history_for_day_trading('ES=F')
print(df)
add = mpf.make_addplot(df['vwap'])
col = mpf.make_marketcolors(up='#2E7D32',down='#D32F2F',inherit=True)
sty = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=col)

kwargs = dict(type='candle', volume=True, style=sty, addplot=add)
mpf.plot(df, **kwargs)