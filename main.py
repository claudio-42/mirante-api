"""
main.py — A API (FastAPI) do Domo Consultoria.

Sobe um servidor que devolve, em JSON, os dados que o front-end React vai desenhar.
Rode com:   uvicorn main:app --reload
Documentação automática em:   http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import core

app = FastAPI(
    title="Domo Consultoria — API de Indicadores Financeiros",
    description="API que serve os dados da camada Gold (CVM/DFP) para o dashboard.",
    version="1.0.0",
)

# CORS: libera o front-end (rodando em outra porta/domínio) a chamar esta API.
# Em produção, troque "*" pela URL do seu site na Vercel.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def raiz():
    return {"ok": True, "servico": "Domo Consultoria API", "docs": "/docs"}


@app.get("/api/health")
def health():
    """Testa se a conexão com o banco está viva."""
    try:
        cat = core.carregar_catalogo()
        return {"ok": True, "empresas": int(len(cat))}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {e}")


@app.get("/api/empresas")
def listar_empresas():
    """Catálogo de empresas (para o seletor): cnpj, razão, setor."""
    try:
        return core.montar_catalogo()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Falha ao listar empresas: {e}")


@app.get("/api/mapa")
def mapa():
    """Empresas com coordenadas (lat/lon) para os pontos do mapa."""
    try:
        return core.montar_mapa()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Falha ao montar o mapa: {e}")


@app.get("/api/empresa")
def detalhe_empresa(cnpj: str):
    """Payload completo de uma empresa: KPIs, indicadores e diagnóstico.

    O CNPJ vai como query param (ex.: /api/empresa?cnpj=67.620.377/0001-14)
    porque ele contém '/' e '.', que quebrariam a rota se fossem no caminho.
    """
    try:
        dados = core.montar_empresa(cnpj)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Falha ao consultar empresa: {e}")
    if dados is None:
        raise HTTPException(status_code=404, detail=f"Sem indicadores para o CNPJ {cnpj}.")
    return dados


@app.get("/api/demonstrativo")
def demonstrativo(cnpj: str, tipo: str):
    """Demonstrativo contábil (tipo = bp | dre | dfc) pivotado por ano."""
    try:
        dados = core.montar_demonstrativo(cnpj, tipo)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Falha ao consultar demonstrativo: {e}")
    if dados is None:
        raise HTTPException(status_code=400, detail="Tipo inválido. Use bp, dre ou dfc.")
    return dados
