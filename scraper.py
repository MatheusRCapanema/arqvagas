import pandas as pd
import os
import re
import requests
import json
from datetime import date

# Tenta importar o Glassdoor scraper (só funciona com Chrome instalado)
try:
    from glassdoor_scraper import buscar_glassdoor_arquitetura
    GLASSDOOR_DISPONIVEL = True
except Exception:
    GLASSDOOR_DISPONIVEL = False

try:
    from jobspy import scrape_jobs
    JOBSPY_DISPONIVEL = True
except Exception:
    JOBSPY_DISPONIVEL = False

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
CSV_PATH = "vagas_aprovadas_ia.csv"

def search_architecture_jobs():
    print("Iniciando a busca por vagas de arquitetura...")
    
    search_terms = [
        "Arquiteto", "Arquitetura", "Arquiteto Junior",
        "Cadista", "Projetista", "BIM", "Revit",
        "Coordenador de Projetos", "Gestor de Obras", "Compatibilizador"
    ]
    locations = ["Distrito Federal, Brasil", "Remote, Brasil"]
    
    negative_skills = [
        "software", "desenvolvedor", "dados", "aws", "cloud",
        "devops", "frontend", "backend", "fullstack", "c#", ".net", "java",
        "javascript", "clean code", "ci/cd", "infraestrutura de ti",
        "machine learning", "kubernetes", "docker",
        "estágio", "estagiário", "estagiario", "estagio"
    ]
    
    all_jobs = []
    
    # --- LinkedIn e Indeed via JobSpy ---
    if JOBSPY_DISPONIVEL:
        for term in search_terms:
            for loc in locations:
                print(f"Buscando '{term}' em '{loc}'...")
                try:
                    jobs = scrape_jobs(
                        site_name=["indeed", "linkedin"],
                        search_term=term,
                        location=loc,
                        results_wanted=1000,
                        hours_old=24,
                        country_indeed="Brazil",
                        linkedin_fetch_description=True
                    )
                    if not jobs.empty:
                        all_jobs.append(jobs)
                except Exception as e:
                    print(f"Erro ao buscar '{term}' em '{loc}': {e}")
    
    # --- Glassdoor via Selenium (somente local) ---
    if GLASSDOOR_DISPONIVEL:
        print("\nIniciando busca no Glassdoor (Selenium)...")
        df_glassdoor = buscar_glassdoor_arquitetura()
        if not df_glassdoor.empty:
            all_jobs.append(df_glassdoor)
    else:
        print("\nGlassdoor indisponível neste ambiente (requer Chrome local).")
        
    if not all_jobs:
        print("Nenhuma vaga encontrada em nenhuma plataforma.")
        return 0
        
    df_all = pd.concat(all_jobs, ignore_index=True)
    df_all.drop_duplicates(subset=['job_url'], inplace=True)
    df_all.to_csv("vagas_brutas.csv", index=False, encoding='utf-8')
    
    print(f"\nTotal de vagas encontradas antes do filtro: {len(df_all)}")
    print("\n--- Fase 2: Filtragem com LLM ---")
    
    padrao_negativo = re.compile(r'\b(' + '|'.join(map(re.escape, negative_skills)) + r')\b')

    def analisar_vaga_llm(titulo, descricao, local):
        descricao_limpa = str(descricao)[:2000]
        
        prompt = f"""
Você é um recrutador sênior especializado em Arquitetura de Edificações e Construção Civil.
Analise a vaga abaixo e retorne APENAS um JSON válido.

Título da Vaga: {titulo}
Local: {local}
Descrição: {descricao_limpa}

HABILIDADES DESEJADAS: Archicad, Sketchup, Autocad, Enscape, Revit, BIM, Pacote Office.

REGRA 1 — e_arquitetura_edificacoes = true APENAS se:
  - A vaga for para Arquiteto(a), Cadista, Desenhista, Projetista, Coordenador/Gestor de projetos de arquitetura ou obras civis
  - OU for vaga técnica em Arquitetura, Engenharia Civil, Construção, Urbanismo, Interiores
  - e_arquitetura_edificacoes = false se for vaga de: VENDAS, RH, Marketing, Financeiro, Administrativo, TI/Software, Médico, Jurídico — mesmo que mencionem "arquitetura" como diferencial ou formação desejável

REGRA 2 — local_correto = true SOMENTE se:
  a) Local é Distrito Federal, Brasília, DF ou cidades-satélite do DF, OU
  b) Vaga for remota, home office, trabalho remoto ou flexível, OU
  c) Local genérico como "Brasil" sem cidade específica, OU
  d) Local não informado
  - local_correto = false se for cidade específica de outro estado (SP, RJ, Recife, Curitiba, etc.) e NÃO for remota

Retorne JSON exato:
{{
  "e_arquitetura_edificacoes": true ou false,
  "local_correto": true ou false,
  "skills_encontradas": ["lista"],
  "motivo": "1 frase explicando"
}}
        """
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek/deepseek-v4-flash:free",  # Modelo gratuito!
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}]
        }
        
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                texto_json = data['choices'][0]['message']['content']
                return json.loads(texto_json)
        except Exception as e:
            print(f"Erro na API: {e}")
        return None

    # Carrega URLs já conhecidas para evitar duplicatas no CSV acumulativo
    urls_ja_salvas = set()
    if os.path.exists(CSV_PATH):
        try:
            df_existente = pd.read_csv(CSV_PATH, encoding='utf-8')
            urls_ja_salvas = set(df_existente['Link'].dropna().tolist())
        except Exception:
            pass

    approved_count = 0
    hoje = date.today().strftime("%d/%m/%Y")

    for index, row in df_all.iterrows():
        descricao = str(row.get('description', ''))
        titulo = str(row.get('title', ''))
        local = str(row.get('location', ''))
        link = str(row.get('job_url', ''))

        # Pula vagas já salvas anteriormente
        if link in urls_ja_salvas:
            continue

        # Filtro negativo local
        descricao_lower = descricao.lower()
        titulo_lower = titulo.lower()
        if padrao_negativo.search(descricao_lower) or padrao_negativo.search(titulo_lower):
            continue
            
        print(f"Analisando com IA: {titulo[:40]}...")
        resultado = analisar_vaga_llm(titulo, descricao, local)
        
        if resultado and resultado.get('e_arquitetura_edificacoes') and resultado.get('local_correto', False):
            # Detecta a plataforma pela URL
            plataforma = "LinkedIn"
            if "indeed" in link:
                plataforma = "Indeed"
            elif "glassdoor" in link:
                plataforma = "Glassdoor"

            vaga_aprovada = {
                'Título': titulo,
                'Empresa': row.get('company', ''),
                'Local': local,
                'Plataforma': plataforma,
                'Skills (IA)': ", ".join(resultado.get('skills_encontradas', [])),
                'Motivo (IA)': resultado.get('motivo', ''),
                'Data': hoje,
                'Link': link
            }
            
            df_temp = pd.DataFrame([vaga_aprovada])
            df_temp.to_csv(CSV_PATH, mode='a', header=not os.path.exists(CSV_PATH), index=False, encoding='utf-8')
            urls_ja_salvas.add(link)
            approved_count += 1
            print(f"  ✅ APROVADA: {titulo[:40]}")

    print(f"\n=== {approved_count} NOVAS VAGAS APROVADAS PELA IA ===")
    if approved_count > 0:
        print(f"Salvas em '{CSV_PATH}'!")
    return approved_count

if __name__ == "__main__":
    search_architecture_jobs()
