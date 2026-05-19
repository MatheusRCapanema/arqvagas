from flask import Flask, jsonify, render_template, request
import pandas as pd
import os
import subprocess
import threading
import requests
from io import StringIO

app = Flask(__name__)

# URL raw do CSV no GitHub (atualiza automaticamente via Actions)
GITHUB_CSV_URL = "https://raw.githubusercontent.com/MatheusRCapanema/arqvagas/main/vagas_aprovadas_ia.csv"
CSV_PATH = "vagas_aprovadas_ia.csv"  # Fallback local

def ler_vagas():
    """Tenta ler do GitHub primeiro; se falhar, lê do disco local."""
    try:
        resp = requests.get(GITHUB_CSV_URL, timeout=10)
        if resp.status_code == 200:
            df = pd.read_csv(StringIO(resp.text))
            df = df.fillna('')
            if 'Data' in df.columns:
                df['Data_sort'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
                df = df.sort_values('Data_sort', ascending=False).drop(columns=['Data_sort'])
            return df.to_dict(orient='records')
    except Exception as e:
        print(f"[GitHub] Erro ao buscar CSV remoto: {e} — usando fallback local.")

    # Fallback: lê do disco local
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH, encoding='utf-8').fillna('')
            if 'Data' in df.columns:
                df['Data_sort'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
                df = df.sort_values('Data_sort', ascending=False).drop(columns=['Data_sort'])
            return df.to_dict(orient='records')
        except Exception as e:
            print(f"[Local] Erro ao ler CSV: {e}")
    return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/vagas')
def api_vagas():
    vagas = ler_vagas()
    return jsonify(vagas)

@app.route('/api/stats')
def api_stats():
    vagas = ler_vagas()
    total = len(vagas)
    com_skills = sum(1 for v in vagas if v.get('Skills (IA)', '').strip())
    remotas = sum(1 for v in vagas if 'remoto' in str(v.get('Local', '')).lower() or 'home office' in str(v.get('Local', '')).lower())
    plataformas = {}
    for v in vagas:
        p = v.get('Plataforma', 'Outro')
        plataformas[p] = plataformas.get(p, 0) + 1
    return jsonify({
        'total': total,
        'com_skills': com_skills,
        'remotas': remotas,
        'plataformas': plataformas
    })

@app.route('/api/historico')
def api_historico():
    vagas = ler_vagas()
    contagem = {}
    for v in vagas:
        data = v.get('Data', 'Sem data')
        contagem[data] = contagem.get(data, 0) + 1
    # Ordena cronologicamente
    resultado = []
    for data, total in sorted(contagem.items(), key=lambda x: pd.to_datetime(x[0], format='%d/%m/%Y', errors='coerce') or pd.Timestamp.min):
        resultado.append({'data': data, 'total': total})
    return jsonify(resultado)

_scraper_rodando = False

@app.route('/api/rodar', methods=['POST'])
def api_rodar():
    """Dispara o scraper manualmente (só funciona com LinkedIn/Indeed no servidor)."""
    global _scraper_rodando
    if _scraper_rodando:
        return jsonify({'status': 'ja_rodando', 'mensagem': 'O robô já está em execução. Aguarde alguns minutos.'})

    def rodar_scraper():
        global _scraper_rodando
        _scraper_rodando = True
        try:
            subprocess.run(['python', 'scraper.py'], timeout=600)
        except Exception as e:
            print(f"Erro ao rodar scraper: {e}")
        finally:
            _scraper_rodando = False

    thread = threading.Thread(target=rodar_scraper, daemon=True)
    thread.start()
    return jsonify({'status': 'iniciado', 'mensagem': 'Robô iniciado! Os dados do GitHub são atualizados automaticamente todo dia às 08h. Use o botão para forçar uma busca agora.'})

@app.route('/api/status')
def api_status():
    return jsonify({'rodando': _scraper_rodando})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
