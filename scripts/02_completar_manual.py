"""
completar_localizacao.py
========================
Preenche as 8 empresas que a BrasilAPI não encontrou, com a sede (município/UF)
verificada manualmente e as coordenadas do IBGE. Roda uma vez, na pasta domo-api:

    python completar_localizacao.py
"""
import json
import os

ARQUIVO = "localizacoes.json"

# Sedes verificadas (matriz). Taurus, Ferrovia Centro-Atlântica e Bradsaúde
# (CNPJ da antiga Odontoprev) foram confirmadas em fontes públicas; as demais
# são sedes amplamente conhecidas dessas companhias abertas.
COMPLEMENTO = {
    "02.351.877/0001-52": {"municipio": "São Paulo",      "uf": "SP", "lat": -23.5329, "lon": -46.6395},  # LWSA (Locaweb)
    "08.764.621/0001-53": {"municipio": "São Paulo",      "uf": "SP", "lat": -23.5329, "lon": -46.6395},  # General Shopping
    "08.343.492/0001-20": {"municipio": "Belo Horizonte", "uf": "MG", "lat": -19.9102, "lon": -43.9266},  # MRV
    "33.592.510/0001-54": {"municipio": "Rio de Janeiro", "uf": "RJ", "lat": -22.9129, "lon": -43.2003},  # Vale
    "92.781.335/0001-02": {"municipio": "São Leopoldo",   "uf": "RS", "lat": -29.7545, "lon": -51.1498},  # Taurus
    "10.629.105/0001-68": {"municipio": "Rio de Janeiro", "uf": "RJ", "lat": -22.9129, "lon": -43.2003},  # PRIO
    "58.119.199/0001-51": {"municipio": "Barueri",        "uf": "SP", "lat": -23.5057, "lon": -46.8790},  # Bradsaúde (ex-Odontoprev)
    "00.924.429/0001-75": {"municipio": "Belo Horizonte", "uf": "MG", "lat": -19.9102, "lon": -43.9266},  # Ferrovia Centro-Atlântica
}


def main():
    if not os.path.exists(ARQUIVO):
        print(f"Arquivo {ARQUIVO} não encontrado. Rode primeiro o enriquecer_localizacao.py.")
        return
    with open(ARQUIVO, encoding="utf-8") as f:
        dados = json.load(f)

    atualizadas = 0
    for cnpj, info in COMPLEMENTO.items():
        if cnpj in dados:
            dados[cnpj].update(info)   # mantém razao_social/setor, completa local + coords
        else:
            dados[cnpj] = info
        atualizadas += 1

    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    com_coord = sum(1 for v in dados.values() if v.get("lat") is not None)
    print(f"{atualizadas} empresas completadas.")
    print(f"Total com coordenada agora: {com_coord} de {len(dados)}.")


if __name__ == "__main__":
    main()
