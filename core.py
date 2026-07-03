"""
core.py — Conexão com o banco, queries e toda a lógica de indicadores/diagnóstico.

Esta é a lógica que JÁ existia no seu app Streamlit, portada para rodar fora dele
(sem `streamlit`). As funções de cálculo e o diagnóstico são praticamente idênticas;
o que mudou foi só remover a dependência do Streamlit e ler as credenciais do .env.
"""
import os
import json
from functools import lru_cache

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ==============================================================================
# Constantes (iguais às do app Streamlit)
# ==============================================================================
GOLD_TABLE = "layer_03_gold.mart_indicadores_financeiros"
MINERVA_CNPJ = "67.620.377/0001-14"

SILVER_BP  = "layer_02_silver.n1_dfp_cia_aberta_bp"
SILVER_DRE = "layer_02_silver.n1_dfp_cia_aberta_dre"
SILVER_DFC = "layer_02_silver.n1_dfp_cia_aberta_dfc"

TABELAS_DEMO = {"bp": SILVER_BP, "dre": SILVER_DRE, "dfc": SILVER_DFC}

KPIS_BP  = [("Ativo Total", "1"), ("Passivo + PL", "2"),
            ("Ativo Circulante", "1.01"), ("Patrimônio Líquido", "2.03")]
KPIS_DRE = [("Receita Líquida", "3.01"), ("Resultado Bruto", "3.03"),
            ("Result. Operacional (EBIT)", "3.05"), ("Lucro/Prejuízo Líquido", "3.11")]
KPIS_DFC = [("Caixa Operacional", "6.01"), ("Caixa de Investimento", "6.02"),
            ("Caixa de Financiamento", "6.03"), ("Variação de Caixa", "6.05")]
KPIS_DEMO = {"bp": KPIS_BP, "dre": KPIS_DRE, "dfc": KPIS_DFC}

INDICADORES = {
    "IND_LIQUIDEZ_GERAL":     dict(label="Liquidez Geral",       grupo="Liquidez",       unidade="idx",   melhor="alto"),
    "IND_LIQUIDEZ_CORRENTE":  dict(label="Liquidez Corrente",    grupo="Liquidez",       unidade="idx",   melhor="alto"),
    "IND_LIQUIDEZ_SECA":      dict(label="Liquidez Seca",        grupo="Liquidez",       unidade="idx",   melhor="alto"),
    "IND_LIQUIDEZ_IMEDIATA":  dict(label="Liquidez Imediata",    grupo="Liquidez",       unidade="idx",   melhor="alto"),
    "IND_PCT_CP":             dict(label="Cap. Terceiros / Cap. Próprio", grupo="Endividamento", unidade="pct", melhor="baixo"),
    "IND_PCT_AT":             dict(label="Cap. Terceiros / Ativo Total",  grupo="Endividamento", unidade="pct", melhor="baixo"),
    "IND_GARANTIA_CT":        dict(label="Garantia Cap. Próprio",         grupo="Endividamento", unidade="pct", melhor="alto"),
    "IND_COMPOSICAO_ENDIV":   dict(label="Composição do Endividamento",   grupo="Endividamento", unidade="pct", melhor="baixo"),
    "IND_IMOB_CP":            dict(label="Imobilização Cap. Próprio",     grupo="Endividamento", unidade="pct", melhor="baixo"),
    "IND_IMOB_AT":            dict(label="Imobilização Ativo Total",      grupo="Endividamento", unidade="pct", melhor="neutro"),
    "IND_MARGEM_BRUTA":       dict(label="Margem Bruta",         grupo="Margens",        unidade="pct",   melhor="alto"),
    "IND_MARGEM_OPERACIONAL": dict(label="Margem Operacional",   grupo="Margens",        unidade="pct",   melhor="alto"),
    "IND_MARGEM_LIQUIDA":     dict(label="Margem Líquida",       grupo="Margens",        unidade="pct",   melhor="alto"),
    "IND_LPA_DILUIDO":        dict(label="LPA (Diluído)",        grupo="Margens",        unidade="rs_ac", melhor="alto"),
    "IND_ROA":                dict(label="ROA",                  grupo="Rentabilidade",  unidade="pct",   melhor="alto"),
    "IND_ROE":                dict(label="ROE",                  grupo="Rentabilidade",  unidade="pct",   melhor="alto"),
    "IND_ROI":                dict(label="ROI",                  grupo="Rentabilidade",  unidade="pct",   melhor="alto"),
    "IND_GIRO_ESTOQUES":      dict(label="Giro de Estoques",     grupo="Atividade",      unidade="vezes", melhor="alto"),
    "IND_GIRO_CR":            dict(label="Giro Contas a Receber",grupo="Atividade",      unidade="vezes", melhor="alto"),
    "IND_GIRO_CP":            dict(label="Giro Contas a Pagar",  grupo="Atividade",      unidade="vezes", melhor="neutro"),
    "IND_GIRO_AC":            dict(label="Giro Ativo Circulante",grupo="Atividade",      unidade="vezes", melhor="alto"),
    "IND_PMRE":               dict(label="PMRE",                 grupo="Atividade",      unidade="dias",  melhor="baixo"),
    "IND_PMRV":               dict(label="PMRV",                 grupo="Atividade",      unidade="dias",  melhor="baixo"),
    "IND_PMPC":               dict(label="PMPC",                 grupo="Atividade",      unidade="dias",  melhor="alto"),
    "IND_PMRAC":              dict(label="PMRAC",                grupo="Atividade",      unidade="dias",  melhor="baixo"),
    "IND_CICLO_ECONOMICO":    dict(label="Ciclo Econômico",      grupo="Ciclos",         unidade="dias",  melhor="baixo"),
    "IND_CICLO_FINANCEIRO":   dict(label="Ciclo Financeiro",     grupo="Ciclos",         unidade="dias",  melhor="baixo"),
    "IND_CGL":                dict(label="Capital de Giro Líquido (CGL)",     grupo="Fleuriet", unidade="rs", melhor="alto"),
    "IND_NCG":                dict(label="Necessidade de Cap. de Giro (NCG)", grupo="Fleuriet", unidade="rs", melhor="neutro"),
    "IND_ST":                 dict(label="Saldo de Tesouraria (ST)",          grupo="Fleuriet", unidade="rs", melhor="alto"),
}

GRUPOS_ORDEM = ["Liquidez", "Endividamento", "Margens", "Rentabilidade", "Atividade", "Ciclos", "Fleuriet"]


# ==============================================================================
# Conexão com o banco (Neon) — singleton com reconexão automática
# ==============================================================================
@lru_cache(maxsize=1)
def get_engine():
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return create_engine(db_url, pool_pre_ping=True, pool_recycle=180)

    from urllib.parse import quote_plus
    user = quote_plus(os.getenv("DB_USER", "postgres"))
    pwd  = quote_plus(os.getenv("DB_PASS", os.getenv("DB_PASSWORD", "")))
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db   = os.getenv("DB_NAME", "postgres")
    return create_engine(f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}",
                         pool_pre_ping=True, pool_recycle=180)


@lru_cache(maxsize=1)
def carregar_catalogo():
    """Catálogo leve: 1 linha por empresa (CNPJ, razão, setor)."""
    engine = get_engine()
    q = text(f'''
        SELECT "CNPJ_CIA",
               MAX("RAZAO_SOCIAL") AS "RAZAO_SOCIAL",
               MAX("SETOR")        AS "SETOR"
        FROM {GOLD_TABLE}
        GROUP BY "CNPJ_CIA";
    ''')
    with engine.connect() as conn:
        cat = pd.read_sql(q, conn)
    cat["CNPJ_CIA"] = cat["CNPJ_CIA"].astype(str)
    cat["RAZAO_SOCIAL"] = cat["RAZAO_SOCIAL"].fillna("(sem razão social)").astype(str)
    cat["SETOR"] = cat["SETOR"].fillna("Sem setor").astype(str)
    return cat.sort_values(["SETOR", "RAZAO_SOCIAL"]).reset_index(drop=True)


@lru_cache(maxsize=128)
def carregar_indicadores(cnpj):
    engine = get_engine()
    q = text(f'SELECT * FROM {GOLD_TABLE} WHERE "CNPJ_CIA" = :cnpj ORDER BY "DT_REFER";')
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params={"cnpj": cnpj})
    if not df.empty:
        df["ANO"] = pd.to_datetime(df["DT_REFER"]).dt.year
    return df


@lru_cache(maxsize=256)
def carregar_demonstrativo(cnpj, tabela):
    engine = get_engine()
    q = text(f'''SELECT "CD_CONTA","DS_CONTA","DT_REFER","VL_CONTA_TRATADO"
                 FROM {tabela}
                 WHERE "CNPJ_CIA" = :cnpj
                 ORDER BY "CD_CONTA","DT_REFER";''')
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params={"cnpj": cnpj})
    if not df.empty:
        df["ANO"] = pd.to_datetime(df["DT_REFER"]).dt.year
        df["CD_CONTA"] = df["CD_CONTA"].astype(str)
    return df


# ==============================================================================
# Formatação (padrão brasileiro) — idêntico ao app
# ==============================================================================
def _br(v, casas=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_rs(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    sinal = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e9: return f"{sinal}R$ {_br(a/1e9, 2)} bi"
    if a >= 1e6: return f"{sinal}R$ {_br(a/1e6, 1)} mi"
    if a >= 1e3: return f"{sinal}R$ {_br(a/1e3, 1)} mil"
    return f"{sinal}R$ {_br(a, 0)}"


def fmt_valor(v, unidade):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    if unidade in ("idx", "vezes"): return f"{_br(v, 2)}×"
    if unidade == "pct":   return f"{_br(v * 100, 1)}%"
    if unidade == "dias":  return f"{_br(v, 0)} dias"
    if unidade == "rs_ac": return f"R$ {_br(v, 2)}"
    if unidade == "rs":    return fmt_rs(v)
    return _br(v)


def fmt_delta(chave, atual, anterior):
    if atual is None or anterior is None or np.isnan(atual) or np.isnan(anterior) or anterior == 0:
        return "—", "neu"
    var = (atual - anterior) / abs(anterior)
    txt = f"{'+' if var >= 0 else ''}{_br(var * 100, 1)}% a/a"
    melhor = INDICADORES.get(chave, {}).get("melhor", "neutro")
    if melhor == "neutro" or abs(var) < 0.001:
        classe = "neu"
    elif (var > 0 and melhor == "alto") or (var < 0 and melhor == "baixo"):
        classe = "pos"
    else:
        classe = "neg"
    return txt, classe


def delta_monetario(atual, anterior):
    if atual is None or anterior is None or np.isnan(atual) or np.isnan(anterior) or anterior == 0:
        return "—", "neu"
    var = (atual - anterior) / abs(anterior)
    txt = f"{'+' if var >= 0 else ''}{_br(var * 100, 1)}% a/a"
    if abs(var) < 0.001:
        return txt, "neu"
    return txt, ("pos" if var > 0 else "neg")


# ==============================================================================
# Classificação por benchmark — idêntico ao app
# ==============================================================================
def classificar(chave, v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "info"
    if chave == "IND_LIQUIDEZ_CORRENTE":  return "good" if v >= 1.5 else ("warn" if v >= 1.0 else "bad")
    if chave == "IND_LIQUIDEZ_GERAL":     return "good" if v >= 1.0 else ("warn" if v >= 0.8 else "bad")
    if chave == "IND_LIQUIDEZ_SECA":      return "good" if v >= 1.0 else ("warn" if v >= 0.7 else "bad")
    if chave == "IND_LIQUIDEZ_IMEDIATA":  return "good" if v >= 0.30 else ("warn" if v >= 0.10 else "bad")
    if chave == "IND_PCT_CP":             return "good" if v <= 1.0 else ("warn" if v <= 2.0 else "bad")
    if chave == "IND_COMPOSICAO_ENDIV":   return "good" if v <= 0.4 else ("warn" if v <= 0.6 else "bad")
    if chave == "IND_IMOB_CP":            return "good" if v <= 1.0 else ("warn" if v <= 1.3 else "bad")
    if chave == "IND_MARGEM_LIQUIDA":     return "good" if v >= 0.05 else ("warn" if v >= 0 else "bad")
    if chave == "IND_MARGEM_OPERACIONAL": return "good" if v >= 0.07 else ("warn" if v >= 0 else "bad")
    if chave in ("IND_ROE", "IND_ROA", "IND_ROI"): return "good" if v >= 0.10 else ("warn" if v >= 0 else "bad")
    if chave == "IND_ST":                 return "good" if v > 0 else "bad"
    if chave == "IND_CICLO_FINANCEIRO":   return "good" if v <= 60 else ("warn" if v <= 120 else "bad")
    return "info"


# ==============================================================================
# Utilitários de série — idêntico ao app
# ==============================================================================
def serie(df, chave):
    if chave not in df.columns:
        return pd.Series(dtype=float)
    return df.set_index("ANO")[chave].sort_index()


def ultimo(df, chave):
    s = serie(df, chave).dropna()
    return (s.index[-1], s.iloc[-1]) if len(s) else (None, np.nan)


def tendencia(s):
    s = s.dropna()
    if len(s) < 2:
        return "insuf"
    var = s.iloc[-1] - s.iloc[0]
    base = abs(s.iloc[0]) if s.iloc[0] != 0 else 1
    if abs(var) / base < 0.05:
        return "estável"
    return "subindo" if var > 0 else "caindo"


def detecta_efeito_tesoura(df):
    s = serie(df, "IND_ST").dropna()
    if len(s) < 3:
        return False
    ult = s.iloc[-3:]
    decrescente = all(ult.iloc[i] > ult.iloc[i + 1] for i in range(len(ult) - 1))
    return decrescente and ult.iloc[-1] < 0


# ==============================================================================
# Contexto setorial + diagnóstico executivo — idêntico ao app
# ==============================================================================
def contexto_setor(setor: str) -> dict:
    s = (setor or "").lower()
    ctx = {
        "liq_apertada": "cobre o curto prazo, mas com margem apertada.",
        "endiv_alto":  "É uma estrutura fortemente alavancada, o que amplia o risco financeiro e a exposição a juros.",
        "endiv_medio": "A dependência de capital de terceiros supera o capital próprio.",
        "endiv_baixo": "O capital próprio ainda supera o de terceiros — estrutura relativamente conservadora.",
        "margem_ctx":  "As margens devem ser lidas à luz do setor de atuação e do momento do ciclo econômico.",
        "margem_baixa_ok": "Margem baixa, mas que pode ser compatível com o modelo de negócio da empresa.",
        "ciclo_nota":  "",
    }
    if any(k in s for k in ["frigor", "carne", "proteí", "proteina", "abate", "bovin", "aves", "suín", "suin"]):
        ctx.update({
            "liq_apertada": "cobre o curto prazo, mas com margem apertada para um frigorífico de ciclo longo.",
            "endiv_alto":  "É uma estrutura fortemente alavancada — comum em frigoríficos pela necessidade de capital de giro e CAPEX, mas que amplia o risco financeiro.",
            "endiv_medio": "A dependência de terceiros supera o capital próprio, padrão típico do setor de proteína animal, intensivo em capital.",
            "endiv_baixo": "O capital próprio ainda supera o de terceiros — estrutura relativamente conservadora para o setor.",
            "margem_ctx":  "O setor de carne opera estruturalmente com margens estreitas e alta sensibilidade ao ciclo do boi, ao câmbio (forte componente exportador) e ao preço da proteína.",
            "margem_baixa_ok": "Margem baixa, mas dentro do que se espera para um frigorífico de grande escala.",
            "ciclo_nota":  " Para frigoríficos, o estoque inclui ativos biológicos, o que tende a alongar o PMRE e o ciclo.",
        })
    elif any(k in s for k in ["varejo", "comérc", "comerc", "loja", "consumo"]):
        ctx.update({
            "margem_ctx":  "O varejo costuma operar com margens líquidas baixas compensadas por alto giro de estoques e de ativos.",
            "margem_baixa_ok": "Margem baixa é a regra no varejo; o que sustenta o retorno é o giro, não a margem unitária.",
            "ciclo_nota":  " No varejo, o giro de estoques e o prazo de fornecedores tendem a dominar o ciclo financeiro.",
        })
    elif any(k in s for k in ["energia", "elétr", "eletr", "utilit", "saneament", "água", "agua", "gás", "gas"]):
        ctx.update({
            "endiv_alto":  "Alavancagem elevada é comum em utilities pela intensidade de CAPEX e pelos contratos de longo prazo; o risco depende da previsibilidade da receita regulada.",
            "margem_ctx":  "Empresas de infraestrutura/utilities costumam ter margens mais estáveis e previsíveis, ligadas a contratos e regulação.",
        })
    elif any(k in s for k in ["banc", "financ", "segur", "crédit", "credit"]):
        ctx.update({
            "endiv_alto":  "Em instituições financeiras a alavancagem é parte do modelo de negócio; indicadores de estrutura de capital tradicionais devem ser lidos com cautela.",
            "margem_ctx":  "Para o setor financeiro, margens e ciclos contábeis tradicionais têm interpretação limitada frente a indicadores próprios do setor.",
        })
    return ctx


def gerar_diagnostico(df, ctx=None):
    if ctx is None:
        ctx = contexto_setor("")
    ins = []

    def add(grupo, nivel, titulo, texto):
        ins.append(dict(grupo=grupo, nivel=nivel, titulo=titulo, texto=texto))

    ano_lc, lc = ultimo(df, "IND_LIQUIDEZ_CORRENTE")
    if not np.isnan(lc):
        nv = classificar("IND_LIQUIDEZ_CORRENTE", lc)
        tend = tendencia(serie(df, "IND_LIQUIDEZ_CORRENTE"))
        base = (f"A liquidez corrente em {ano_lc} é de {fmt_valor(lc,'idx')}, ou seja, R$ {_br(lc,2)} de "
                f"ativo circulante para cada R$ 1,00 de dívida de curto prazo.")
        if nv == "good":
            txt = base + " Está acima da referência confortável de 1,5×, indicando folga para honrar obrigações imediatas."
        elif nv == "warn":
            txt = base + " Situa-se entre 1,0× e 1,5× — " + ctx["liq_apertada"]
        else:
            txt = base + " Abaixo de 1,0×, sinaliza que o passivo circulante supera o ativo circulante — pressão de caixa relevante."
        if tend != "insuf":
            txt += f" A trajetória recente é de {('melhora' if tend=='subindo' else 'piora' if tend=='caindo' else 'estabilidade')} do índice."
        add("Liquidez", nv, "Liquidez de curto prazo", txt)

    ano_e, pct_cp = ultimo(df, "IND_PCT_CP")
    _, comp = ultimo(df, "IND_COMPOSICAO_ENDIV")
    if not np.isnan(pct_cp):
        nv = classificar("IND_PCT_CP", pct_cp)
        txt = f"Em {ano_e}, o capital de terceiros equivale a {fmt_valor(pct_cp,'pct')} do capital próprio. "
        if pct_cp > 2.0:
            txt += ctx["endiv_alto"]
        elif pct_cp > 1.0:
            txt += ctx["endiv_medio"]
        else:
            txt += ctx["endiv_baixo"]
        if not np.isnan(comp):
            txt += (f" Da dívida total, {fmt_valor(comp,'pct')} vence no curto prazo"
                    + (" — concentração elevada, que exige liquidez para rolagem." if comp > 0.6
                       else " — perfil de prazo equilibrado."))
        add("Endividamento", nv, "Estrutura de capital e endividamento", txt)

    ano_r, roe = ultimo(df, "IND_ROE")
    _, roa = ultimo(df, "IND_ROA")
    _, pl = ultimo(df, "V12_PL")
    if not np.isnan(roe):
        if not np.isnan(pl) and pl < 0:
            add("Rentabilidade", "bad", "Rentabilidade sobre o patrimônio",
                f"O Patrimônio Líquido está negativo em {ano_r} ({fmt_rs(pl)}). Nesse cenário o ROE perde "
                f"significado econômico e deve ser interpretado junto ao ROA e à estrutura de capital.")
        else:
            nv = classificar("IND_ROE", roe)
            txt = f"O ROE de {ano_r} é de {fmt_valor(roe,'pct')}"
            if not np.isnan(roa):
                spread = (roe - roa) * 100
                txt += (f", contra um ROA de {fmt_valor(roa,'pct')}. O diferencial de {_br(spread,1)} p.p. reflete o "
                        f"{'efeito favorável' if spread > 0 else 'efeito desfavorável'} da alavancagem: a dívida "
                        f"{'amplia' if spread > 0 else 'corrói'} o retorno do acionista.")
            else:
                txt += "."
            add("Rentabilidade", nv, "Rentabilidade sobre o patrimônio", txt)

    ano_m, ml = ultimo(df, "IND_MARGEM_LIQUIDA")
    if not np.isnan(ml):
        nv = classificar("IND_MARGEM_LIQUIDA", ml)
        txt = (f"A margem líquida de {ano_m} é de {fmt_valor(ml,'pct')}. " + ctx["margem_ctx"] + " ")
        if ml < 0:
            txt += "O resultado negativo no período indica que custos e despesas superaram a receita líquida."
        elif ml < 0.05:
            txt += ctx["margem_baixa_ok"]
        else:
            txt += "Margem saudável para o padrão do setor."
        add("Margens", nv, "Margem e contexto setorial", txt)

    ano_c, cf = ultimo(df, "IND_CICLO_FINANCEIRO")
    if not np.isnan(cf):
        nv = classificar("IND_CICLO_FINANCEIRO", cf)
        if cf < 0:
            txt = (f"O ciclo financeiro de {ano_c} é negativo ({_br(cf,0)} dias): a empresa recebe das vendas antes "
                   f"de pagar fornecedores, situação de autofinanciamento operacional.")
        else:
            txt = (f"O ciclo financeiro de {ano_c} é de {fmt_valor(cf,'dias')} — período em que o caixa fica "
                   f"comprometido entre pagar fornecedores e receber das vendas." + ctx["ciclo_nota"])
        add("Ciclos", nv, "Ciclo financeiro e capital de giro", txt)

    ano_st, st_v = ultimo(df, "IND_ST")
    _, cgl = ultimo(df, "IND_CGL")
    _, ncg = ultimo(df, "IND_NCG")
    if not np.isnan(st_v):
        if detecta_efeito_tesoura(df):
            add("Fleuriet", "bad", "Alerta: possível Efeito Tesoura",
                f"O Saldo de Tesouraria vem se deteriorando de forma sucessiva e está negativo em {ano_st} "
                f"({fmt_rs(st_v)}). A configuração clássica do Efeito Tesoura indica que a NCG cresce mais rápido que "
                f"o CGL, exigindo financiamento de curto prazo crescente — sinal de atenção para a saúde financeira.")
        else:
            nv = "good" if st_v > 0 else "warn"
            txt = f"O Saldo de Tesouraria de {ano_st} é {fmt_rs(st_v)}"
            if not np.isnan(ncg) and not np.isnan(cgl):
                txt += (f", resultado de um CGL de {fmt_rs(cgl)} frente a uma NCG de {fmt_rs(ncg)}. "
                        f"{'A folga financeira cobre a necessidade operacional de giro.' if st_v > 0 else 'A necessidade de giro consome a folga de curto prazo, exigindo recursos onerosos.'}")
            else:
                txt += "."
            add("Fleuriet", nv, "Modelo dinâmico (Fleuriet)", txt)

    return ins


# ==============================================================================
# Montagem dos payloads JSON (o que a API devolve para o React)
# ==============================================================================
def _num(v):
    """Converte numpy/NaN para tipos nativos seguros para JSON (NaN -> None)."""
    if v is None:
        return None
    try:
        if isinstance(v, float) and np.isnan(v):
            return None
        if isinstance(v, (np.floating, np.integer)):
            v = v.item()
        if isinstance(v, float) and np.isnan(v):
            return None
    except Exception:
        return None
    return v


def _limpa_nome(razao: str) -> str:
    import re
    n = (razao or "").strip()
    n = re.sub(r"\b(S\.?\s*/?\s*A\.?|LTDA\.?|EIRELI|EPP|CIA\.?|COMPANHIA|HOLDING|PARTICIPACOES|PARTICIPAÇÕES)\b",
               "", n, flags=re.I)
    n = re.sub(r"\s*\.\s*", " ", n)
    n = re.sub(r"\s{2,}", " ", n).strip(" .,-/")
    if not n:
        return razao or "Empresa"
    return " ".join(w if (len(w) <= 3 and w.isupper()) else w.capitalize() for w in n.split())


def montar_catalogo():
    cat = carregar_catalogo()
    empresas = [
        {"cnpj": r.CNPJ_CIA, "razao_social": r.RAZAO_SOCIAL,
         "razao_limpa": _limpa_nome(r.RAZAO_SOCIAL), "setor": r.SETOR}
        for r in cat.itertuples()
        if r.RAZAO_SOCIAL and not str(r.RAZAO_SOCIAL).strip().lower().startswith("(sem")
    ]
    setores = sorted({e["setor"] for e in empresas})
    return {"empresas": empresas, "setores": setores, "total": len(empresas)}


def _kpis_visao_geral(df):
    """KPIs da aba Visão Geral (mesmos do app)."""
    specs = [
        ("Receita Líquida", "V17_RECEITA_LIQ", "rs", "mon"),
        ("Lucro Líquido", "V21_LUCRO_LIQ", "rs", "mon"),
        ("Margem Líquida", "IND_MARGEM_LIQUIDA", "pct", "ind"),
        ("ROE", "IND_ROE", "pct", "ind"),
        ("Liquidez Corrente", "IND_LIQUIDEZ_CORRENTE", "idx", "ind"),
        ("Ciclo Financeiro", "IND_CICLO_FINANCEIRO", "dias", "ind"),
    ]
    kpis = []
    for label, chave, unidade, tipo in specs:
        s = serie(df, chave).dropna()
        if len(s) == 0:
            kpis.append({"label": label, "valor": None, "valor_fmt": "N/A",
                         "delta_txt": "—", "delta_classe": "neu"})
            continue
        atual = s.iloc[-1]
        anterior = s.iloc[-2] if len(s) >= 2 else np.nan
        if tipo == "mon":
            dtxt, dcls = delta_monetario(atual, anterior)
        else:
            dtxt, dcls = fmt_delta(chave, atual, anterior)
        kpis.append({
            "label": label,
            "valor": _num(atual),
            "valor_fmt": fmt_valor(atual, unidade),
            "delta_txt": dtxt,
            "delta_classe": dcls,
        })
    return kpis


def montar_empresa(cnpj):
    """Payload completo de uma empresa para o dashboard."""
    df = carregar_indicadores(cnpj)
    if df.empty:
        return None

    cat = carregar_catalogo()
    linha = cat[cat["CNPJ_CIA"] == cnpj]
    razao = (str(df["RAZAO_SOCIAL"].dropna().iloc[0]) if "RAZAO_SOCIAL" in df and df["RAZAO_SOCIAL"].notna().any()
             else (str(linha["RAZAO_SOCIAL"].iloc[0]) if not linha.empty else cnpj))
    setor = (str(df["SETOR"].dropna().iloc[0]) if "SETOR" in df and df["SETOR"].notna().any()
             else (str(linha["SETOR"].iloc[0]) if not linha.empty else "Sem setor"))

    anos = sorted(int(a) for a in df["ANO"].unique())
    ctx = contexto_setor(setor)

    # indicadores: série + metadados + classificação do último ano
    indicadores = []
    for chave, meta in INDICADORES.items():
        if chave not in df.columns:
            continue
        s = serie(df, chave)
        serie_json = [{"ano": int(a), "valor": _num(v),
                       "valor_fmt": fmt_valor(v, meta["unidade"]) if not (isinstance(v, float) and np.isnan(v)) else "N/A"}
                      for a, v in s.items()]
        ano_u, val_u = ultimo(df, chave)
        anterior = np.nan
        sd = s.dropna()
        if len(sd) >= 2:
            anterior = sd.iloc[-2]
        dtxt, dcls = fmt_delta(chave, val_u, anterior)
        indicadores.append({
            "chave": chave,
            "label": meta["label"],
            "grupo": meta["grupo"],
            "unidade": meta["unidade"],
            "melhor": meta["melhor"],
            "serie": serie_json,
            "ultimo": {
                "ano": int(ano_u) if ano_u is not None else None,
                "valor": _num(val_u),
                "valor_fmt": fmt_valor(val_u, meta["unidade"]),
                "classe": classificar(chave, val_u),
            },
            "delta": {"txt": dtxt, "classe": dcls},
            "tendencia": tendencia(s),
        })

    return {
        "empresa": {
            "cnpj": cnpj,
            "razao_social": razao,
            "razao_limpa": _limpa_nome(razao),
            "setor": setor,
        },
        "anos": anos,
        "kpis": _kpis_visao_geral(df),
        "indicadores": indicadores,
        "grupos": GRUPOS_ORDEM,
        "diagnostico": gerar_diagnostico(df, ctx),
    }


def montar_demonstrativo(cnpj, tipo):
    """Demonstrativo (bp/dre/dfc) pivotado por ano + KPIs do demonstrativo."""
    tipo = tipo.lower()
    if tipo not in TABELAS_DEMO:
        return None
    dfl = carregar_demonstrativo(cnpj, TABELAS_DEMO[tipo])
    if dfl.empty:
        return {"tipo": tipo, "anos": [], "kpis": [], "contas": []}

    anos = sorted(int(a) for a in dfl["ANO"].unique())
    ano_cur = anos[-1]

    # KPIs do demonstrativo
    kpis = []
    for label, cd in KPIS_DEMO[tipo]:
        m = dfl[(dfl["CD_CONTA"] == cd) & (dfl["ANO"] == ano_cur)]
        valor = float(m["VL_CONTA_TRATADO"].iloc[0]) if not m.empty else np.nan
        kpis.append({"label": label, "valor": _num(valor), "valor_fmt": fmt_rs(valor)})

    # tabela de contas (todas), com valores por ano
    contas = []
    for (cd, ds), grupo in dfl.groupby(["CD_CONTA", "DS_CONTA"]):
        valores = {}
        for a in anos:
            mm = grupo[grupo["ANO"] == a]
            valores[str(a)] = _num(float(mm["VL_CONTA_TRATADO"].iloc[0])) if not mm.empty else None
        contas.append({
            "cd_conta": cd,
            "ds_conta": ds,
            "nivel": str(cd).count(".") + 1,
            "valores": valores,
        })
    contas.sort(key=lambda c: [int(p) if p.isdigit() else 0 for p in c["cd_conta"].split(".")])

    return {"tipo": tipo, "ano_atual": ano_cur, "anos": anos, "kpis": kpis, "contas": contas}


# ==============================================================================
# Mapa — localização das empresas (lê o localizacoes.json gerado pelos scripts)
# ==============================================================================
LOCALIZACOES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "localizacoes.json")


@lru_cache(maxsize=1)
def montar_mapa():
    """Empresas com coordenadas, para os pontos no mapa da landing."""
    if not os.path.exists(LOCALIZACOES_PATH):
        return {"empresas": [], "setores": [], "total": 0, "sem_localizacao": 0}
    with open(LOCALIZACOES_PATH, encoding="utf-8") as f:
        loc = json.load(f)
    empresas = []
    for cnpj, v in loc.items():
        if v.get("lat") is None or v.get("lon") is None:
            continue
        razao = v.get("razao_social")
        if not razao or razao.strip().lower().startswith("(sem"):
            continue  # oculta empresas sem razão social
        empresas.append({
            "cnpj": cnpj,
            "razao_social": v.get("razao_social"),
            "razao_limpa": _limpa_nome(v.get("razao_social") or cnpj),
            "setor": v.get("setor") or "Sem setor",
            "municipio": v.get("municipio"),
            "uf": v.get("uf"),
            "lat": v.get("lat"),
            "lon": v.get("lon"),
        })
    empresas.sort(key=lambda e: e["razao_limpa"])
    setores = sorted({e["setor"] for e in empresas})
    sem = sum(1 for v in loc.values() if v.get("lat") is None)
    return {"empresas": empresas, "setores": setores, "total": len(empresas), "sem_localizacao": sem}
