from flask import Flask, render_template, request, jsonify, send_file
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import calculations as cl
import downloader as dw
from plotly.subplots import make_subplots
from alpha_vantage.timeseries import TimeSeries
import io

app = Flask(__name__)
ticker_list = dw.ticker_list
csv_to_download = pd.DataFrame()


# Rota para buscar tickers que correspondem ao input
@app.route('/search_ticker', methods=['GET'])
def search_ticker():
    query = request.args.get('query', '').upper()  # Pega a busca do usuário
    # Filtra a lista de tickers baseada no que o usuário digitou
    suggestions = [ticker for ticker in ticker_list if query in ticker]
    return jsonify(suggestions)


@app.route('/carteira')
def carteira():
    return render_template('carteira.html')


def get_data(ticker, start_date, end_date, aporte_mensal, aporte_inicial, engine, api_key, benchmark):
    data = cl.results(ticker, start_date, end_date, engine=engine, aporte_mensal=aporte_mensal,
                      aporte_inicial=aporte_inicial, api_key=api_key, benchmark=benchmark)
    return data


# Função para buscar dados do Alpha Vantage
def fetch_alpha_vantage_data(ticker, api_key):
    ts = TimeSeries(key=api_key, output_format='pandas')
    data, _ = ts.get_daily(symbol=ticker, outputsize='full')
    return data


# Rota para a página inicial
@app.route('/', methods=['GET', 'POST'])
def index():
    graphJSON = None
    data = None
    if request.method == 'POST':
        ticker = request.form['ticker']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        source = request.form['source']
        aporte_inicial = float((request.form['aporte_inicial']).replace(",", "."))
        aporte_mensal = float((request.form['aporte_mensal']).replace(",", "."))
        benchmark = request.form['benchmark']

        data = get_data(ticker, start_date, end_date, engine=source, aporte_mensal=aporte_mensal,
                        aporte_inicial=aporte_inicial, api_key='<KEY>', benchmark=benchmark)

        # if source == 'yfinance':
        #     data = fetch_yfinance_data(ticker, start_date, end_date)
        # elif source == 'Alpha Vantage':
        #     api_key = 'SUA_API_KEY'  # Substitua pela sua chave de API
        #     data = fetch_alpha_vantage_data(ticker, api_key)

        # Verifica se o DataFrame contém dados
        if data is not None and not data.empty:
            # Calcula a média entre 'Close' e 'Open'
            data['Avg'] = (data['Close'] + data['Open']) / 2

            # Cria um subplot com duas linhas e uma coluna
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                subplot_titles=('Gráfico de Preços', 'Análise de Investimento'),
                                vertical_spacing=0.1)

            # Adiciona o primeiro gráfico: Preços
            fig.add_trace(go.Scatter(x=data.index, y=data['Close'], mode='lines', name='Close Price'),
                          row=1, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=data['Open'], mode='lines', name='Open Price'),
                          row=1, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=data['Avg'], mode='lines', name='Average Price'),
                          row=1, col=1)
            # fig.add_trace(go.Scatter(x=data.index, y=data['Adj Close'], mode='lines', name='Adjusted Close'), row=1, col=1)

            # Adiciona o segundo gráfico: Valor Investido e Valor Final
            fig.add_trace(go.Scatter(x=data.index, y=data['Valor Investido'], mode='lines', name='Valor Investido'),
                          row=2, col=1)
            fig.add_trace(go.Scatter(x=data.index, y=data['Valor Final'], mode='lines', name='Valor Final'),
                          row=2, col=1)
            if benchmark != 'none':
                fig.add_trace(go.Scatter(x=data.index, y=data['Bench'], mode='lines', name='Benchmark ({})'.format(benchmark)),
                              row=2, col=1)

            # Atualiza o layout dos gráficos
            fig.update_layout(title_text=f'{ticker} - {start_date} a {end_date}')

            # Converte para JSON para renderização no template
            graphJSON = fig.to_json()

            global csv_to_download
            csv_to_download = data.copy()  # Armazena uma cópia do DataFrame para download

    return render_template('index.html', graphJSON=graphJSON, data=data)


# data['Valor Investido']
@app.route('/download', methods=['GET'])
def download():
    # Cria um buffer em memória para o CSV
    csv_buffer = io.StringIO()
    csv_to_download.to_csv(csv_buffer, index=False)  # Converte o DataFrame para CSV
    csv_buffer.seek(0)  # Retorna ao início do buffer

    # Retorna o CSV como um arquivo para download
    return send_file(
        io.BytesIO(csv_buffer.getvalue().encode()),  # Converte o buffer para bytes
        mimetype='text/csv',
        as_attachment=True,
        download_name='data.csv'
    )


if __name__ == '__main__':
    app.run(debug=True)
