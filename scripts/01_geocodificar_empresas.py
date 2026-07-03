"""
enriquecer_localizacao.py
=========================
Pega os CNPJs da sua base (camada Gold, no Neon), consulta a sede (município/UF)
de cada um na BrasilAPI (dado oficial da Receita Federal) e cruza com a base de
municípios do IBGE para obter latitude/longitude. Salva tudo em `localizacoes.json`.

Roda UMA vez. Se for interrompido (rate limit, queda), é só rodar de novo: ele
retoma de onde parou (não reconsulta o que já foi feito).

Como rodar (na pasta domo-api, com o venv ativo):
    pip install requests
    python enriquecer_localizacao.py
"""
import csv
import io
import json
import os
import re
import time
import unicodedata

import requests

import core  # reutiliza a conexão com o banco e o catálogo de empresas

ARQUIVO_SAIDA = "localizacoes.json"
URL_MUNICIPIOS = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
URL_ESTADOS = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/estados.csv"
PAUSA_ENTRE_CHAMADAS = 1.5   # segundos entre consultas (evita rate limit da BrasilAPI)
SALVAR_A_CADA = 10           # grava o progresso a cada N empresas


def normalizar(s: str) -> str:
    """Remove acentos, deixa maiúsculo e tira espaços das pontas."""
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper().strip()


def baixar_csv(url: str):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))


def carregar_indice_municipios():
    """Monta o índice (município normalizado, UF) -> (lat, lon) a partir do IBGE."""
    print("Baixando base de municípios do IBGE...")
    mun = baixar_csv(URL_MUNICIPIOS)
    est = baixar_csv(URL_ESTADOS)
    uf_por_codigo = {r["codigo_uf"]: r["uf"] for r in est}
    indice = {}
    for r in mun:
        uf = uf_por_codigo.get(r["codigo_uf"])
        chave = (normalizar(r["nome"]), uf)
        indice[chave] = (float(r["latitude"]), float(r["longitude"]))
    print(f"  {len(indice)} municípios carregados.\n")
    return indice


def consultar_cnpj(cnpj_digitos: str):
    """Consulta a BrasilAPI. Devolve (municipio, uf) ou (None, None)."""
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_digitos}"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    for tentativa in range(4):
        try:
            r = requests.get(url, headers=headers, timeout=25)
        except requests.RequestException:
            time.sleep(5)
            continue
        if r.status_code == 200:
            d = r.json()
            return d.get("municipio"), d.get("uf")
        if r.status_code == 404:
            return None, None  # CNPJ não encontrado na Receita
        if r.status_code == 429:
            espera = 20 * (tentativa + 1)
            print(f"    rate limit; aguardando {espera}s...")
            time.sleep(espera)
            continue
        time.sleep(5)
    return None, None


def main():
    cat = core.carregar_catalogo()  # CNPJ_CIA, RAZAO_SOCIAL, SETOR
    indice_mun = carregar_indice_municipios()

    # retoma progresso anterior, se houver
    resultado = {}
    if os.path.exists(ARQUIVO_SAIDA):
        with open(ARQUIVO_SAIDA, encoding="utf-8") as f:
            resultado = json.load(f)
        print(f"Retomando: {len(resultado)} empresas já processadas.\n")

    total = len(cat)
    for i, row in enumerate(cat.itertuples(), start=1):
        cnpj = row.CNPJ_CIA
        if cnpj in resultado and resultado[cnpj].get("lat") is not None:
            continue  # já tem coordenada, pula

        dig = re.sub(r"\D", "", cnpj)
        municipio, uf = consultar_cnpj(dig)
        lat = lon = None
        if municipio and uf:
            lat_lon = indice_mun.get((normalizar(municipio), uf))
            if lat_lon:
                lat, lon = lat_lon

        resultado[cnpj] = {
            "razao_social": row.RAZAO_SOCIAL,
            "setor": row.SETOR,
            "municipio": municipio,
            "uf": uf,
            "lat": lat,
            "lon": lon,
        }
        status = "OK" if lat is not None else ("sem coord" if municipio else "não encontrado")
        print(f"[{i:>3}/{total}] {cnpj}  {str(municipio or '-'):<22} {uf or '--'}  -> {status}")

        if i % SALVAR_A_CADA == 0:
            with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
                json.dump(resultado, f, ensure_ascii=False, indent=2)

        time.sleep(PAUSA_ENTRE_CHAMADAS)

    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    # resumo
    com_coord = sum(1 for v in resultado.values() if v.get("lat") is not None)
    sem_coord = sum(1 for v in resultado.values() if v.get("lat") is None and v.get("municipio"))
    nao_achou = sum(1 for v in resultado.values() if not v.get("municipio"))
    print("\n================ RESUMO ================")
    print(f"  Total de empresas........: {len(resultado)}")
    print(f"  Com coordenada (no mapa).: {com_coord}")
    print(f"  Sem coordenada (sede ok, município não casou): {sem_coord}")
    print(f"  CNPJ não encontrado......: {nao_achou}")
    print(f"\nArquivo gerado: {ARQUIVO_SAIDA}")
    if sem_coord or nao_achou:
        print("As poucas que faltaram você pode completar manualmente no JSON depois.")


if __name__ == "__main__":
    main()