# Domo Consultoria — API (Backend)

API em **FastAPI** que serve os dados da camada Gold (CVM/DFP) para o front-end React.
Toda a lógica de indicadores e diagnóstico foi reaproveitada do app Streamlit.

## O que ela faz

Expõe estes endpoints (a documentação interativa fica em `/docs`):

| Método | Rota | O que devolve |
|--------|------|---------------|
| GET | `/api/health` | Testa a conexão com o banco |
| GET | `/api/empresas` | Catálogo de empresas (cnpj, razão, setor) — para o seletor |
| GET | `/api/empresa?cnpj=...` | Payload completo: KPIs, indicadores (com série e classificação) e diagnóstico |
| GET | `/api/demonstrativo?cnpj=...&tipo=bp\|dre\|dfc` | Demonstrativo pivotado por ano |

> O CNPJ vai como parâmetro de query (`?cnpj=...`) porque contém `/` e `.`.

## Como rodar (Windows)

**1. Abra o terminal nesta pasta.** No explorador de arquivos, entre na pasta `domo-api`,
clique na barra de endereço, digite `cmd` e aperte Enter.

**2. Crie um ambiente virtual e instale as dependências:**
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configure o banco.** Renomeie o arquivo `.env.example` para `.env` e cole dentro
a sua connection string do Neon (a versão **com** `-pooler`, sem o `&channel_binding`):
```
DATABASE_URL=postgresql://neondb_owner:SUA_SENHA@ep-...-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require
```

**4. Suba a API:**
```
uvicorn main:app --reload
```

**5. Teste no navegador.** Abra:
- http://127.0.0.1:8000/docs  → documentação interativa (clique em "Try it out")
- http://127.0.0.1:8000/api/empresas  → deve aparecer a lista de empresas em JSON

Se aparecer o JSON com as empresas, o backend está funcionando e conectado ao Neon. 🎉

## Estrutura

```
domo-api/
├── main.py            # A API (endpoints + CORS)
├── core.py            # Conexão com o banco + queries + lógica de indicadores/diagnóstico
├── requirements.txt   # Dependências
├── .env.example       # Modelo de configuração (renomeie para .env)
└── README.md
```

## Próximos passos

- **Fase 2:** front-end React + Tremor consumindo esta API.
- **Fase 3:** deploy do backend (Render) e do front-end (Vercel).
