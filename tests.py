from flask import Flask, render_template, request
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from alpha_vantage.timeseries import TimeSeries
from datetime import datetime, timedelta
from decimal import Decimal, getcontext
import holidays
import math

getcontext().prec = 20

def benchy(benchmark):
    df_benchy = pd.read_csv('database/gallywix/benchmarks/benchy_diario.csv', sep=';')
    df_benchy['Date'] = pd.to_datetime(df_benchy['Date'], format='%d/%m/%Y')
    return df_benchy[['Date', benchmark]]


def truncate(num, decimals=16):
    d = Decimal(str(num))
    # Trunca para 16 casas decimais sem arredondar
    return d.quantize(Decimal('1e-{0}'.format(decimals)))


def calculo_CDI(data, start_date, end_date):
    start_date = datetime.strptime(start_date, "%d/%m/%Y")
    end_date = datetime.strptime(end_date, "%d/%m/%Y")

    df = data[(data['Date'] >= start_date) & (
                data['Date'] < end_date)]  # A data final é "exclusive" enquanto a inicial é "inclusive"
    C = 1
    dias_uteis = 252
    taxa_rendimento = 100.0000

    for line in range(len(df)):
        if df.iloc[line]['Date'].year > 1997:
            TDIk = round((((df.iloc[line]['DI'] / 100) + 1) ** (1 / dias_uteis)) - 1, 8) # Taxa DI Over
            print(TDIk)
        else:
            TDIk = round(df.iloc[line]['DI'] / 3000, 8)
        C_daily = truncate((1 + (TDIk * (taxa_rendimento / 100))), 16)
        C = truncate(C * C_daily, 16)

    return C


# Testando as funções
benchmark_table = benchy("DI")
resultado_CDI = calculo_CDI(benchmark_table, start_date="01/01/2024", end_date="07/11/2024")
print("Resultado CDI:", round(resultado_CDI, 8))
