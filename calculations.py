from flask import Flask, render_template, request
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from alpha_vantage.timeseries import TimeSeries
from datetime import datetime, timedelta
import holidays
import math


def feriados():
    # Obter feriados do estado de São Paulo
    sp_holidays = holidays.Brazil(years=[x for x in range(1995, (datetime.now()).year + 1)], prov='SP')
    sp_date = []
    for date, name in sorted(sp_holidays.items()):
        sp_date.append(date.strftime('%Y-%m-%d'))
    return sp_date  # Retorna um conjunto de datas


def benchy(benchmark):
    df_benchy = pd.read_csv('database/gallywix/benchmarks/benchy_diario.csv', sep=';')
    df_benchy['Date'] = pd.to_datetime(df_benchy['Date'], format='%d/%m/%Y')
    return df_benchy[['Date', benchmark]]


def results(ticker="ITSA4.SA", start_date="2024-01-01", end_date="2024-12-31", aporte_inicial=4200, aporte_mensal=4200,
            engine="yfinance", api_key="", benchmark="none"):
    # Serve para arrumar alguns dados que estão em "NaN":
    bonus_date = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
    benchy_table = benchy(benchmark)

    if engine == "Gallywix":
        data = pd.read_csv("database/gallywix/stocks/" + ticker + ".csv")
        temp_data = data.copy()
        filtered_temp_data = temp_data[(temp_data['Date'] >= bonus_date) & (temp_data['Date'] <= end_date)]
        data = data.loc[filtered_temp_data.index]
        data.set_index('Date', inplace=True)
    elif engine == "yfinance":
        data = yf.Ticker(ticker).history(start=bonus_date, end=end_date)
    elif engine == "alpha-vantage":
        ts = TimeSeries(key=api_key, output_format='pandas')
        data, _ = ts.get_daily(symbol=ticker, outputsize='full')

    data.index = pd.to_datetime(data.index)  # Convert index to datetime
    data = data.resample('D').asfreq()  # Resample data to include all days

    data['Index_numerico'] = range(len(data))

    # Fill missing values with the previous values
    data = data.ffill()  # Forward fill to fill gaps with previous values

    data = data[data.index >= start_date]

    # Adicionar uma coluna com o dia da semana (segunda-feira = 0, domingo = 6)
    data['week'] = data.index.weekday

    # Calcula a média entre 'Close' e 'Open'
    data['Avg'] = (data['Close'] + data['Open']) / 2

    # Preenche valores inválidos na coluna 'Avg' com a média dos preços dos dias anterior e seguinte
    data['Avg'] = data['Avg'].interpolate(method='linear', limit_direction='both')

    # Inicializa as colunas de cálculo no DataFrame `data`
    data['Valor Investido'] = 0
    data['Saldo Restante'] = 0

    data['Week'] = data.index.to_series().dt.weekday  # Segeunda-feira = 0, Domingo = 6, Sábado = 5
    data['Date'] = data.index.strftime('%Y-%m-%d')

    # Necessário para descobrir se o dia em questão foi feriado ou fim de semana, assim jogaremos a "compra" das ações
    # para o próximo dia útil.
    sp_feriados = feriados()
    valid_date = []
    for num in range(0, len(data)):
        if data['Week'].iloc[num] == 5 or data['Week'].iloc[num] == 6:  # Sábado ou Domingo
            valid_date.append(False)
        elif data["Date"].iloc[num] in sp_feriados:  # Data é um feriado
            valid_date.append(False)
        else:
            valid_date.append(True)

    data['Dia_Util'] = valid_date
    data['Date'] = pd.to_datetime(data['Date'])

    # Agora o banco de dados está pronto para iniciar os cálculos.
    aporte_diario = []  # Coluna que colocará o valor aportado naquele dia.
    somatorio_de_aportes = []  # Coluna para realizar o somatório de aportes
    dinheiro_em_conta = []  # Coluna que colocará as "sobras" paradas no banco.
    dinheiro_investido = []  # Coluna que somará o total de dinheiro investido na ação.
    dinheiro_total = []  # Somatória do dinheiro investido com o dinheiro em conta.
    qtd_acoes = []  # Quantidade de ações compradas
    benchmark_final = [] # Valor acumulado para o benchmark

    # Iniciando os trabalhos:

    aporte_diario.append(aporte_inicial)
    somatorio_de_aportes.append(aporte_inicial)
    qtd_acoes.append(math.floor((aporte_diario[0] / data['Avg'].iloc[0])))
    dinheiro_investido.append(qtd_acoes[0] * data['Avg'].iloc[0])
    dinheiro_em_conta.append(aporte_diario[0] - dinheiro_investido[0])
    dinheiro_total.append(dinheiro_investido[0] + dinheiro_em_conta[0])
    benchmark_final.append(somatorio_de_aportes[0])

    day = 1
    # Coloca os aportes nos dias corretos:

    while day < len(data):
        if day % 31 == 0:
            flag = 0
            while flag == 0:
                if data['Dia_Util'].iloc[day]:
                    aporte_diario.append(aporte_mensal)
                    flag = 1
                    day += 1
                else:
                    aporte_diario.append(0)
                    day += 1
        else:
            aporte_diario.append(0)
            day += 1
    for line in range(1, len(data)):
        somatorio_de_aportes.append(somatorio_de_aportes[line - 1] + aporte_diario[line])

        termo_novo = (math.floor((aporte_diario[line] / data['Avg'].iloc[
            line])))  # Novas ações compradas diariamente, baseado no aporte diario.
        termo_resto = math.floor(dinheiro_em_conta[line - 1] / data['Avg'].iloc[
            line])  # Ações compradas diariamente baseado no restante que sobra em caixa.
        qtd_acoes.append(termo_novo + qtd_acoes[line - 1] + termo_resto)  # Vetor de ações compradas no dia "line"

        dinheiro_investido.append(
            qtd_acoes[line] * data['Avg'].iloc[line])  # Vetor de somatória de dinheiro investido no dia "Line"

        resta_aporte = (aporte_diario[line] - termo_novo * data['Avg'].iloc[
            line])  # Valor que resta do aporte, após investimento.
        resta_resto = (dinheiro_em_conta[line - 1] - termo_resto * data['Avg'].iloc[
            line])  # Valor que resta do resto do dia anterior, após aporte de dinheiro em conta.
        if data['Dividends'].iloc[
            line - 1] == 0:  # Essa linha considera que é impossível receber dividendos 2 dias seguidos, por isso é tratado.
            dividendo_total = data['Dividends'].iloc[line] * qtd_acoes[line - 1]  # Valor total de dividendos recebidos.
        else:
            dividendo_total = 0

        dinheiro_em_conta.append(dividendo_total + resta_aporte + resta_resto)  # Valor em conta.
        dinheiro_total.append(dinheiro_em_conta[line] + dinheiro_investido[
            line])  # Dinheiro total, somando a conta e o dinheiro investido.

    # for num in range(0, len(data)):

    # for date in data.index:
    #
    #     # Obtém o número de meses desde o início
    #     num_months = (date.year - pd.to_datetime(start_date).year) * 12 + date.month - pd.to_datetime(start_date).month
    #
    #     # Calcula o valor total investido
    #     total_investido = aporte_inicial + aporte_mensal * num_months
    #
    #     # Obtém o preço médio mais recente
    #     preco_acao = data.loc[date, 'Avg']
    #
    #     if preco_acao > 0:
    #         # Calcula a quantidade de ações que pode ser comprada
    #         quantidade_acoes = total_investido // preco_acao
    #         valor_gasto = quantidade_acoes * preco_acao
    #
    #         # Atualiza o valor investido e o saldo restante
    #         data.loc[date, 'Valor Investido'] = valor_gasto
    #         data.loc[date, 'Saldo Restante'] = total_investido - valor_gasto
    #     else:
    #         # Se o preço da ação for zero ou inválido, o valor investido é o total disponível
    #         data.loc[date, 'Valor Investido'] = total_investido
    #         data.loc[date, 'Saldo Restante'] = 0
    #
    # # Adiciona a coluna 'Valor de Mercado' com base no preço médio
    # data['Valor de Mercado'] = data.index.to_series().map(
    #     lambda x: data.loc[:x, 'Avg'].iloc[-1] if not data.loc[:x, 'Avg'].empty else 0)
    #
    # # Calcula o valor final do investimento
    # data['Valor Final'] = data['Valor Investido'] * data['Valor de Mercado'] / data['Avg'].iloc[0]

    data['Aporte_Diario'] = aporte_diario
    data["Valor Investido"] = somatorio_de_aportes
    data["Qtd_Acoes_Compradas"] = qtd_acoes
    data["Dinheiro_Investido"] = dinheiro_investido
    data["Dinheiro_Em_Conta"] = dinheiro_em_conta
    data["Valor Final"] = dinheiro_total
    data['Bench'] = data['Date'].map(benchy_table.set_index('Date')[benchmark])

    return data


# Exemplo de uso
# print(results())
# dataframe = results()

# dataframe.to_csv("output.csv")
