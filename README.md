# Mirante — API (Backend)

API em **FastAPI** que serve dados financeiros de empresas (camada Gold, CVM/DFP) para o front-end web do Mirante. Toda a lógica de indicadores e diagnóstico foi portada de um app Streamlit original, sem depender mais do Streamlit.

## Sobre o projeto

O Mirante consome dados públicos da CVM (Comissão de Valores Mobiliários) já tratados em um pipeline de dados (camadas Silver/Gold) e expõe, via API, indicadores financeiros, demonstrativos contábeis e diagnóstico executivo automatizado de empresas de capital aberto. O banco de dados roda no [Neon](https://neon.tech) (Postgres serverless).

## Stack

- **FastAPI** — servidor HTTP e documentação automática
- **SQLAlchemy + psycopg2** — conexão com o Postgres (Neon)
- **pandas / numpy** — cálculo de indicadores e séries históricas
- **python-dotenv** — carregamento de variáveis de ambiente

## O que a API faz

Documentação interativa disponível em `/docs` (Swagger UI).

| Método | Rota | O que devolve |
| ------ | ---- | -------------- |
| GET | `/api/health` | Testa a conexão com o banco |
| GET | `/api/empresas` | Catálogo de empresas (CNPJ, razão social, setor) — para o seletor |
| GET | `/api/mapa` | Empresas com coordenadas (lat/lon) para os pontos do mapa |
| GET | `/api/empresa?cnpj=...` | Payload completo: KPIs, indicadores (série histórica + classificação) e diagnóstico executivo |
| GET | `/api/demonstrativo?cnpj=...&tipo=bp\|dre\|dfc` | Demonstrativo contábil (Balanço, DRE ou DFC) pivotado por ano |

> O CNPJ vai como parâmetro de query (`?cnpj=...`), pois contém `/` e `.`, o que quebraria a rota se fosse parte do caminho.

## Como rodar localmente

**1. Clone o repositório e entre na pasta:**

```bash
git clone https://github.com/claudio-42/mirante-api.git
cd mirante-api
```

**2. Crie um ambiente virtual e instale as dependências:**

Windows:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Linux/macOS:
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Configure o banco.** Crie um arquivo `.env` na raiz do projeto com a sua connection string do Neon (use a versão **com** `-pooler`, sem o parâmetro `&channel_binding`):

```
DATABASE_URL=postgresql://neondb_owner:SUA_SENHA@ep-...-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require
```

**4. Suba a API:**

```
uvicorn main:app --reload
```

**5. Teste no navegador:**

- `http://127.0.0.1:8000/docs` → documentação interativa (clique em "Try it out")
- `http://127.0.0.1:8000/api/empresas` → deve retornar a lista de empresas em JSON

Se o JSON com as empresas aparecer, o backend está funcionando e conectado ao Neon. 🎉

## Estrutura

```
mirante-api/
├── main.py             # A API (endpoints + CORS)
├── core.py              # Conexão com o banco + queries + lógica de indicadores/diagnóstico
├── scripts/              # Scripts auxiliares (ex.: geração de localizacoes.json)
├── localizacoes.json     # Coordenadas das empresas, usadas pelo endpoint /api/mapa
├── requirements.txt      # Dependências
└── README.md
```

## Próximos passos

- **Deploy:** publicar o backend (Render) e o front-end (Vercel).
- **Cobertura de dados:** ampliar o catálogo de empresas e setores.

---

Projeto pessoal desenvolvido por [claudio-42](https://github.com/claudio-42).
