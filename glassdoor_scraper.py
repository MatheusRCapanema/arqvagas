"""
Scraper do Glassdoor usando Selenium (Chrome headless).
Abre um navegador real para contornar as proteções anti-bot.
"""
import time
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def criar_driver():
    """Cria um driver Chrome stealth para evitar detecção."""
    options = Options()
    options.add_argument("--headless=new")  # Invisível
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    # Remove o atributo webdriver para não ser detectado
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def scrape_glassdoor(search_term: str, location: str = "Distrito Federal") -> list[dict]:
    """
    Raspa vagas do Glassdoor para um determinado termo e localização.
    Retorna uma lista de dicionários com as vagas encontradas.
    """
    vagas = []
    driver = criar_driver()

    # URL correta do Glassdoor Brasil (padrão /Vaga/ descoberto por inspeção)
    # Exemplo: /Vaga/distrito-federal-brasil-arquiteto-vagas-SRCH_IL.0,23_IS3921_KO24,33.htm
    # Usamos uma URL mais genérica que funciona sem o código IS da cidade
    termo_slug = search_term.lower().replace(" ", "-")
    local_slug = location.lower().replace(" ", "-")
    local_len = len(local_slug)
    termo_start = local_len + 1
    termo_end = termo_start + len(search_term)
    url = (
        f"https://www.glassdoor.com.br/Vaga/{local_slug}-brasil-{termo_slug}-vagas"
        f"-SRCH_IL.0,{local_len+7}_KO{local_len+8},{local_len+8+len(search_term)}.htm"
    )

    try:
        print(f"  [Glassdoor] Acessando: {search_term} em {location}...")
        driver.get(url)
        time.sleep(random.uniform(3, 5))

        wait = WebDriverWait(driver, 15)

        # Fecha o popup de login se aparecer
        try:
            fechar = driver.find_element(By.CSS_SELECTOR, "[alt='Close'], [data-test='modal-close-btn'], .modal_closeIcon")
            fechar.click()
            time.sleep(1)
        except Exception:
            pass

        # Aguarda o container de vagas aparecer
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "li[data-jobid], [data-test='jobListing']")))

        cards = driver.find_elements(By.CSS_SELECTOR, "li[data-jobid], [data-test='jobListing']")
        print(f"  [Glassdoor] {len(cards)} cards encontrados.")

        for card in cards[:30]:  # Limita para não sobrecarregar
            try:
                # Seletores atuais do Glassdoor Brasil
                titulo = card.find_element(By.CSS_SELECTOR, "a.JobCard_jobTitle__GLyJ1, [data-test='job-title'], .job-title").text.strip()
                
                try:
                    empresa = card.find_element(By.CSS_SELECTOR, ".EmployerProfile_employerName__Xemli, .employer-name, [data-test='employer-name']").text.strip()
                except Exception:
                    empresa = ""
                
                try:
                    local = card.find_element(By.CSS_SELECTOR, ".JobCard_location__Ds1fM, [data-test='emp-location'], .location").text.strip()
                except Exception:
                    local = ""

                try:
                    link_el = card.find_element(By.CSS_SELECTOR, "a.JobCard_jobTitle__GLyJ1, a[data-test='job-title']")
                    link = link_el.get_attribute("href") or driver.current_url
                except Exception:
                    link = driver.current_url

                # Tenta pegar o snippet de descrição que já aparece no card
                try:
                    descricao = card.find_element(By.CSS_SELECTOR, ".JobCard_jobDescriptionSnippet__yWe9C, .job-snippet, [data-test='descriptionSnippet']").text.strip()
                except Exception:
                    descricao = ""

                vagas.append({
                    "title": titulo,
                    "company": empresa,
                    "location": local,
                    "description": descricao,
                    "job_url": link,
                    "site": "glassdoor"
                })

            except Exception:
                continue

    except Exception as e:
        print(f"  [Glassdoor] Erro durante busca: {e}")
    finally:
        driver.quit()

    return vagas


def buscar_glassdoor_arquitetura() -> pd.DataFrame:
    """
    Faz a busca completa no Glassdoor para todos os termos e locais de interesse.
    """
    search_terms = ["Arquitetura", "Arquiteto", "Cadista", "Arquiteto Junior"]
    locations = ["Distrito Federal"]

    todos = []
    for term in search_terms:
        for loc in locations:
            vagas = scrape_glassdoor(term, loc)
            todos.extend(vagas)

    if not todos:
        print("[Glassdoor] Nenhuma vaga encontrada.")
        return pd.DataFrame()

    df = pd.DataFrame(todos)
    df.drop_duplicates(subset=["job_url"], inplace=True)
    print(f"[Glassdoor] Total único após deduplicação: {len(df)}")
    return df


if __name__ == "__main__":
    df = buscar_glassdoor_arquitetura()
    if not df.empty:
        df.to_csv("vagas_glassdoor_raw.csv", index=False, encoding="utf-8")
        print(df[["title", "company", "location"]].to_string())
