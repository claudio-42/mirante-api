# Mirante API

API em FastAPI que serve os indicadores financeiros de companhias abertas da B3 (dados CVM/DFP) em formato JSON, para o front-end do Mirante. É a camada intermediária entre o banco de dados (PostgreSQL/Neon) e a interface em React.

**Documentação interativa (ao vivo):** https://mirante-api.onrender.com/docs

> A API está hospedada no Render (plano gratuito) e hiberna após um período ocioso; a primeira requisição pode levar de 30 a 60 segundos para "acordar" o serviço.

Este projeto faz parte de um sistema em três camadas:

- **Pipeline de dados (CVM):** [bigdata_for_finance](https://github.com/claudio-42/bigdata_for_finance) — constrói a base
- **API (este repositório):** consome a base e a expõe em JSON
- **Front-end React:** [mirante-web](https://github.com/claudio-42/mirante-web) — consome esta API

---

## Endpoints

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/api/health` | Testa a conexão com o banco |
| GET | `/api/empresas` | Catálogo de empresas (cnpj, razão, setor) |
| GET | `/api/mapa` | Empresas com coordenadas (lat/lon) para o mapa |
| GET | `/api/empresa?cnpj=...` | Payload completo de uma empresa: KPIs, indicadores e diagnóstico |
| GET | `/api/demonstrativo?cnpj=...&tipo=bp\|dre\|dfc` | Demonstrativo contábil pivotado por ano |

> O CNPJ vai como parâmetro de query (`?cnpj=...`) porque contém `/` e `.`.

A documentação completa e testável de cada endpoint fica em `/docs` (Swagger, gerado automaticamente pelo FastAPI).

---

## Tecnologias

Python, FastAPI, Uvicorn, SQLAlchemy, psycopg2, pandas. Banco PostgreSQL hospedado no Neon. Deploy no Render.

---

## Como rodar localmente

A API não funciona sozinha: ela precisa de um banco PostgreSQL já populado com as camadas Silver e Gold (a "receita" da análise financeira). Esses dados são públicos da CVM e são construídos pelo pipeline em [bigdata_for_finance](https://github.com/claudio-42/bigdata_for_finance).

**Pré-requisitos:** Python 3.12, e um banco PostgreSQL com as camadas Silver e Gold (construídas via o pipeline acima, ou um dump próprio).

1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Crie um arquivo `.env` na raiz com a connection string do seu banco (formato — nunca versione este arquivo):
   ```
   DATABASE_URL=postgresql://usuario:senha@host:5432/nome_do_banco
   ```
   (Para Neon, use a string do connection pooler, terminando em `?sslmode=require`.)
3. Suba a API:
   ```bash
   uvicorn main:app --reload
   ```
4. Acesse a documentação em `http://127.0.0.1:8000/docs`.

---

## Estrutura

```
mirante-api/
├── scripts/                        Ferramentas de preparação de dados (uso único)
│   ├── 01_geocodificar_empresas.py   Geocodifica as sedes via BrasilAPI + IBGE
│   └── 02_completar_manual.py        Completa manualmente as empresas não encontradas
├── core.py                         Conexão, queries e lógica de indicadores/diagnóstico
├── main.py                         Definição da API (endpoints e CORS)
├── localizacoes.json               Coordenadas das empresas (gerado pelos scripts)
├── requirements.txt
├── .python-version                 Fixa o Python 3.12 para o deploy
├── .gitignore
└── README.md
```

---

## Deploy (Render)

- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Variável de ambiente:** `DATABASE_URL` (connection string do Neon)
- A versão do Python é fixada em 3.12 pelo arquivo `.python-version`.

---

*Parte do projeto Mirante, desenvolvido a partir da disciplina de Big Data for Finance. Dados públicos da CVM; finalidade acadêmica, não constitui recomendação de investimento.*
