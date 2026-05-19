from flask import Flask, jsonify, render_template, request
import pandas as pd
import os
import subprocess
import threading

app = Flask(__name__)
CSV_PATH = "vagas_aprovadas_ia.csv"

def ler_vagas():
    if not os.path.exists(CSV_PATH):
        return []
    try:
        df = pd.read_csv(CSV_PATH, encoding='utf-8')
        df = df.fillna('')
        # Ordenar por data (mais recente primeiro)
        if 'Data' in df.columns:
            df['Data_sort'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
            df = df.sort_values('Data_sort', ascending=False).drop(columns=['Data_sort'])
        return df.to_dict(orient='records')
    except Exception as e:
        print(f"Erro ao ler CSV: {e}")
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

_scraper_rodando = False

@app.route('/api/rodar', methods=['POST'])
def api_rodar():
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
    return jsonify({'status': 'iniciado', 'mensagem': 'O robô foi iniciado! As novas vagas aparecerão em alguns minutos.'})

@app.route('/api/status')
def api_status():
    return jsonify({'rodando': _scraper_rodando})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
