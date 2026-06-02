
import json
import re
import unicodedata
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# DASHBOARD MASTER BRUNA — V12
# Mescla:
# - V6 Executivo + Mapa IA
# - V9 Executivo / clusters
# - V10 Agenda Estratégica
# - V11 Consolidado
# - V11 Digital Intelligence + Relatórios
#
# Não exclui funcionalidades: apenas acrescenta abas e leituras.
# ============================================================


# -----------------------------
# Arquivos esperados/opcionais
# -----------------------------
BASE_V9 = "municipios_consolidados_v9_cluster.csv"
BASE_V10 = "agenda_v10_campanha.csv"
BASE_V6_POLITICO = "base_modelo_bruna_v6_politico.csv"
BASE_V6_REAL_ALT = "base_modelo_v6_politico_real.csv"
BASE_V3_IA = "base_modelo_bruna_v3_ia.csv"
BASE_V3_REAL = "base_modelo_bruna_v3_real.csv"
BASE_V4 = "base_modelo_bruna_v4_unificada.csv"
BASE_V5 = "base_modelo_bruna_v5_recalibrada.csv"

METRICAS_V6 = "metricas_modelo_ia_v6.json"
METRICAS_IA = "metricas_modelo_ia.json"
IMPORTANCIAS_IA = "importancias_modelo_ia.csv"
GEOJSON_FILE = "ma_municipios.geojson"

BASE_DIGITAL_MENCOES = "base_sentimento_bruna_v11_classificada.csv"
BASE_DIGITAL_SEED = "base_sentimento_bruna_v11_seed_publica.csv"
BASE_DIGITAL_MUNICIPIOS = "isd_municipios_bruna_v11.csv"


# -----------------------------
# Cores e mapeamentos
# -----------------------------
CORES_CLUSTER = {
    "Sustentação": "#d73027",
    "Expansão quente": "#fc8d59",
    "Presença estratégica": "#fee08b",
    "Custo alto": "#91bfdb",
}

CORES_AGENDA = {
    "Agenda imediata": "#d73027",
    "Agenda prioritária": "#fc8d59",
    "Agenda seletiva": "#fee08b",
    "Presença institucional": "#91bfdb",
    "Sem classificação": "#bdbdbd",
}

MAPEAMENTO_MANUAL = {
    "santa filomena do ma": "São Filomena do Maranhão",
    "santa filomena do maranhao": "Santa Filomena do Maranhão",
    "sao domingos do ma": "São Domingos do Maranhão",
    "capinzal": "Capinzal do Norte",
    "gov eugenio barros": "Governador Eugênio Barros",
    "sao luis gonzaga do ma": "São Luís Gonzaga do Maranhão",
    "s raimundo das mangabeiras": "São Raimundo das Mangabeiras",
    "amarante do ma": "Amarante do Maranhão",
    "pres juscelino": "Presidente Juscelino",
    "sao benedito": "São Benedito do Rio Preto",
    "gov nunes freire": "Governador Nunes Freire",
    "ribeiraozinho edison lobao": "Edison Lobão",
}


# -----------------------------
# Utilitários
# -----------------------------
def normalizar_nome(texto) -> str:
    if pd.isna(texto):
        return ""
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-z0-9]+", " ", texto).strip()
    return texto


def fmt_int(v):
    try:
        return f"{int(round(float(v))):,}".replace(",", ".")
    except Exception:
        return "0"


def fmt_float(v, casas=1):
    try:
        return f"{float(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0"


def prioridade_label(p):
    mapa = {
        "A": "Prioridade máxima",
        "B": "Prioridade alta",
        "C": "Prioridade média",
        "D": "Prioridade baixa",
    }
    return mapa.get(str(p), str(p))


def col_exists(df, col):
    return isinstance(df, pd.DataFrame) and not df.empty and col in df.columns


def primeira_coluna(df, candidatas):
    for c in candidatas:
        if col_exists(df, c):
            return c
    return None


def escolher_base_existente(candidatas):
    for path in candidatas:
        if Path(path).exists():
            return path
    return None


@st.cache_data
def carregar_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data
def carregar_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def tentar_csv(path: str) -> pd.DataFrame:
    if path and Path(path).exists():
        try:
            return carregar_csv(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def tentar_json(path: str) -> dict:
    if path and Path(path).exists():
        try:
            return carregar_json(path)
        except Exception:
            return {}
    return {}


def preparar_mapa_generico(df: pd.DataFrame, geojson: dict, coluna_municipio: str = "CIDADE") -> pd.DataFrame:
    if df.empty or not geojson or coluna_municipio not in df.columns:
        return df

    geo_map = {}
    for feat in geojson.get("features", []):
        nome = feat["properties"].get("NM_MUN")
        codigo = feat["properties"].get("CD_MUN")
        geo_map[normalizar_nome(nome)] = codigo

    mapeamento_norm = {normalizar_nome(k): normalizar_nome(v) for k, v in MAPEAMENTO_MANUAL.items()}

    out = df.copy()
    out["cidade_norm"] = out[coluna_municipio].apply(normalizar_nome)
    out["cidade_norm"] = out["cidade_norm"].replace(mapeamento_norm)
    out["cd_mun"] = out["cidade_norm"].map(geo_map)
    out["mapa_ok"] = out["cd_mun"].notna()
    return out


def normalizar_coluna_municipio(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "CIDADE" not in out.columns:
        if "municipio" in out.columns:
            out["CIDADE"] = out["municipio"]
        elif "Município" in out.columns:
            out["CIDADE"] = out["Município"]
        elif "cidade" in out.columns:
            out["CIDADE"] = out["cidade"]
    if "municipio" not in out.columns and "CIDADE" in out.columns:
        out["municipio"] = out["CIDADE"]
    return out


def normalizar_0_100(s):
    s = pd.to_numeric(s, errors="coerce").fillna(0)
    if len(s) == 0:
        return s
    if s.max() == s.min():
        return pd.Series([50] * len(s), index=s.index)
    return ((s - s.min()) / (s.max() - s.min()) * 100).clip(0, 100)


# -----------------------------
# Consolidação das bases V9/V10/V6/Digital
# -----------------------------
def consolidar_v9_v10(df_v9, df_v10):
    df_v9 = normalizar_coluna_municipio(df_v9)
    df_v10 = normalizar_coluna_municipio(df_v10)

    if df_v9.empty and not df_v10.empty:
        df = df_v10.copy()
    elif df_v10.empty and not df_v9.empty:
        df = df_v9.copy()
    elif not df_v9.empty and not df_v10.empty:
        v9 = df_v9.copy()
        v10 = df_v10.copy()
        v9["cidade_norm_join"] = v9["CIDADE"].apply(normalizar_nome)
        v10["cidade_norm_join"] = v10["CIDADE"].apply(normalizar_nome)

        colunas_v10 = [
            "cidade_norm_join", "prioridade_agenda", "agenda_score", "cluster_v9",
            "acao_recomendada", "expectativa_total", "eficiencia_eleitoral",
        ]
        colunas_v10 = [c for c in colunas_v10 if c in v10.columns]

        df = v9.merge(
            v10[colunas_v10],
            on="cidade_norm_join",
            how="outer",
            suffixes=("", "_v10"),
        )

        if "CIDADE" not in df.columns and "CIDADE_v10" in df.columns:
            df["CIDADE"] = df["CIDADE_v10"]

        for base_col in ["cluster_v9", "acao_recomendada", "expectativa_total", "eficiencia_eleitoral"]:
            col_v10 = f"{base_col}_v10"
            if col_v10 in df.columns:
                if base_col in df.columns:
                    df[base_col] = df[col_v10].combine_first(df[base_col])
                else:
                    df[base_col] = df[col_v10]
                df = df.drop(columns=[col_v10])
    else:
        return pd.DataFrame()

    df = normalizar_coluna_municipio(df)

    if "prioridade_agenda" not in df.columns:
        df["prioridade_agenda"] = "Sem classificação"
    df["prioridade_agenda"] = df["prioridade_agenda"].fillna("Sem classificação")

    if "agenda_score" not in df.columns:
        df["agenda_score"] = df.get("score_municipal_v8", 0)

    for c in ["agenda_score", "score_municipal_v8", "expectativa_total", "eficiencia_eleitoral"]:
        if c not in df.columns:
            df[c] = 0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    if "cluster_v9" not in df.columns:
        df["cluster_v9"] = "Sem cluster"
    df["cluster_v9"] = df["cluster_v9"].fillna("Sem cluster")

    if "acao_recomendada" not in df.columns:
        df["acao_recomendada"] = "Não informado"

    df["indice_consolidado"] = (
        0.55 * df["agenda_score"]
        + 0.30 * df["score_municipal_v8"]
        + 0.15 * df["eficiencia_eleitoral"]
    )

    return df


def carregar_bases_digitais():
    men_path = BASE_DIGITAL_MENCOES if Path(BASE_DIGITAL_MENCOES).exists() else BASE_DIGITAL_SEED
    df_mencoes = tentar_csv(men_path)
    df_mun = tentar_csv(BASE_DIGITAL_MUNICIPIOS)

    # Se só existir base seed, calcula os campos básicos em memória.
    if not df_mencoes.empty and df_mun.empty:
        for col in ["sentimento_score", "engajamento_publico_est", "alcance_territorial_est", "rejeicao_est"]:
            if col in df_mencoes.columns:
                df_mencoes[col] = pd.to_numeric(df_mencoes[col], errors="coerce").fillna(0)

        if "isd_mencao" not in df_mencoes.columns:
            df_mencoes["isd_mencao"] = (
                0.40 * df_mencoes.get("sentimento_score", 50)
                + 0.25 * df_mencoes.get("engajamento_publico_est", 50)
                + 0.25 * df_mencoes.get("alcance_territorial_est", 50)
                - 0.10 * df_mencoes.get("rejeicao_est", 25)
            ).clip(0, 100)

        if "municipio" in df_mencoes.columns:
            df_mun = (
                df_mencoes.groupby("municipio", dropna=False)
                .agg(
                    qtd_mencoes=("municipio", "count"),
                    sentimento_medio=("sentimento_score", "mean"),
                    engajamento_medio=("engajamento_publico_est", "mean"),
                    alcance_medio=("alcance_territorial_est", "mean"),
                    rejeicao_media=("rejeicao_est", "mean"),
                    isd_medio=("isd_mencao", "mean"),
                    fontes=("fonte", lambda x: "; ".join(sorted(set(map(str, x)))) if "fonte" in df_mencoes.columns else ""),
                    temas=("temas", lambda x: "; ".join(sorted(set(";".join(map(str, x)).split(";")))) if "temas" in df_mencoes.columns else ""),
                )
                .reset_index()
            )
            df_mun["volume_mencoes_score"] = normalizar_0_100(df_mun["qtd_mencoes"])
            df_mun["isd_v11"] = (0.85 * df_mun["isd_medio"] + 0.15 * df_mun["volume_mencoes_score"]).round(2)

            def classificar(v):
                if v >= 75:
                    return "Muito favorável"
                if v >= 60:
                    return "Favorável"
                if v >= 45:
                    return "Neutro/instável"
                if v >= 30:
                    return "Alerta"
                return "Crítico"

            df_mun["classificacao_isd"] = df_mun["isd_v11"].apply(classificar)

    df_mencoes = normalizar_coluna_municipio(df_mencoes)
    df_mun = normalizar_coluna_municipio(df_mun)
    return df_mencoes, df_mun


def integrar_digital(df_base, df_digital_mun):
    if df_base.empty or df_digital_mun.empty:
        return df_base

    df = df_base.copy()
    dig = df_digital_mun.copy()

    df["cidade_norm_join"] = df["CIDADE"].apply(normalizar_nome)
    dig["cidade_norm_join"] = dig["CIDADE"].apply(normalizar_nome)

    cols = [
        "cidade_norm_join", "qtd_mencoes", "sentimento_medio", "engajamento_medio",
        "alcance_medio", "rejeicao_media", "isd_v11", "classificacao_isd",
        "fontes", "temas",
    ]
    cols = [c for c in cols if c in dig.columns]

    df = df.merge(dig[cols], on="cidade_norm_join", how="left")

    for c in ["qtd_mencoes", "sentimento_medio", "engajamento_medio", "alcance_medio", "rejeicao_media", "isd_v11"]:
        if c not in df.columns:
            df[c] = 0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    if "classificacao_isd" not in df.columns:
        df["classificacao_isd"] = "Sem dados digitais"
    df["classificacao_isd"] = df["classificacao_isd"].fillna("Sem dados digitais")

    df["indice_master_v12"] = (
        0.70 * df.get("indice_consolidado", 0)
        + 0.30 * df.get("isd_v11", 0)
    )
    return df


# -----------------------------
# Relatórios
# -----------------------------
def classificar_cenario(isd):
    if isd >= 75:
        return "muito favorável"
    if isd >= 60:
        return "favorável"
    if isd >= 45:
        return "neutro ou instável"
    if isd >= 30:
        return "em alerta"
    return "crítico"


def interpretar_municipio_digital(row):
    municipio = row.get("municipio", row.get("CIDADE", "Município"))
    isd = float(row.get("isd_v11", 0))
    sentimento = float(row.get("sentimento_medio", 0))
    rejeicao = float(row.get("rejeicao_media", 0))
    mencoes = int(float(row.get("qtd_mencoes", 0)))
    classificacao = row.get("classificacao_isd", "Sem dados digitais")

    if mencoes <= 0:
        return f"**{municipio}** ainda não possui menções digitais suficientes na base pública. Recomendação: ampliar coleta de fontes locais e redes abertas."

    leitura = (
        f"**{municipio}** apresenta ISD de **{fmt_float(isd)}**, classificado como "
        f"**{classificacao}**. A leitura indica um ambiente digital **{classificar_cenario(isd)}** "
        f"nas fontes públicas analisadas."
    )
    detalhes = (
        f"Foram encontradas **{mencoes} menção(ões)** pública(s). "
        f"O sentimento médio ficou em **{fmt_float(sentimento)}** e a rejeição média estimada em "
        f"**{fmt_float(rejeicao)}**."
    )
    if isd >= 75:
        acao = "Recomendação: transformar esse território em vitrine de narrativa positiva, reforçando agendas, registros visuais e depoimentos locais."
    elif isd >= 60:
        acao = "Recomendação: manter presença contínua e ampliar a produção de conteúdo local para consolidar o sentimento favorável."
    elif isd >= 45:
        acao = "Recomendação: aumentar escuta territorial, publicar conteúdos mais próximos da realidade local e observar sinais de crítica."
    else:
        acao = "Recomendação: acompanhar com atenção, identificar causas de rejeição e evitar exposição sem preparação narrativa."
    return leitura + "\n\n" + detalhes + "\n\n" + acao


def resumo_executivo_digital(mun, df_mencoes):
    if mun.empty or df_mencoes.empty:
        return "Ainda não há base digital carregada. Coloque os arquivos digitais V11 na mesma pasta para ativar este relatório."

    total_mencoes = len(df_mencoes)
    municipios = mun["CIDADE"].nunique() if "CIDADE" in mun.columns else mun["municipio"].nunique()
    isd_medio = mun["isd_v11"].mean() if "isd_v11" in mun.columns else 0
    rejeicao_media = mun["rejeicao_media"].mean() if "rejeicao_media" in mun.columns else 0

    positivos = (df_mencoes.get("sentimento_label", pd.Series(dtype=str)).astype(str).str.lower() == "positivo").sum()
    negativos = (df_mencoes.get("sentimento_label", pd.Series(dtype=str)).astype(str).str.lower() == "negativo").sum()
    neutros = (df_mencoes.get("sentimento_label", pd.Series(dtype=str)).astype(str).str.lower() == "neutro").sum()

    top = mun.sort_values("isd_v11", ascending=False).head(3) if "isd_v11" in mun.columns else mun.head(0)
    alerta = mun.sort_values("isd_v11", ascending=True).head(3) if "isd_v11" in mun.columns else mun.head(0)

    def nome_row(r):
        return r.get("CIDADE", r.get("municipio", ""))

    texto = f"""
### Leitura executiva digital

A base pública analisada contém **{total_mencoes} menções** distribuídas em **{municipios} município(s)**.
O **ISD médio** ficou em **{fmt_float(isd_medio)}**, enquanto a **rejeição média estimada** foi de **{fmt_float(rejeicao_media)}**.

No conjunto da amostra, foram classificadas **{positivos} menções positivas**, **{neutros} neutras** e **{negativos} negativas**.

**Municípios com melhor ambiente digital:**  
{", ".join([f"{nome_row(r)} ({fmt_float(r['isd_v11'])})" for _, r in top.iterrows()])}

**Municípios que exigem atenção:**  
{", ".join([f"{nome_row(r)} ({fmt_float(r['isd_v11'])})" for _, r in alerta.iterrows()])}

Este índice mede **sentimento público observável em fontes abertas**, não intenção de voto.
"""
    return texto


def gerar_relatorio_master(df, df_dig_mun, df_mencoes):
    linhas = []
    linhas.append("# Relatório Master — Bruna V12")
    linhas.append(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    linhas.append("")
    linhas.append("## Síntese geral")
    if not df.empty:
        linhas.append(f"- Municípios analisados: {len(df)}")
        if "expectativa_total" in df.columns:
            linhas.append(f"- Meta total: {fmt_int(df['expectativa_total'].sum())}")
        if "indice_consolidado" in df.columns:
            linhas.append(f"- Índice consolidado médio: {fmt_float(df['indice_consolidado'].mean())}")
        if "indice_master_v12" in df.columns:
            linhas.append(f"- Índice Master V12 médio: {fmt_float(df['indice_master_v12'].mean())}")
    linhas.append("")
    linhas.append("## Inteligência Digital")
    linhas.append(resumo_executivo_digital(df_dig_mun, df_mencoes))
    linhas.append("")
    linhas.append("## Leitura dos municípios com maior prioridade")
    if not df.empty:
        ordem = "indice_master_v12" if "indice_master_v12" in df.columns else "indice_consolidado"
        for _, r in df.sort_values(ordem, ascending=False).head(15).iterrows():
            linhas.append(f"### {r.get('CIDADE', r.get('municipio', 'Município'))}")
            linhas.append(f"- Cluster: {r.get('cluster_v9', 'Não informado')}")
            linhas.append(f"- Agenda: {r.get('prioridade_agenda', 'Não informado')}")
            linhas.append(f"- Ação recomendada: {r.get('acao_recomendada', 'Não informado')}")
            if "isd_v11" in r:
                linhas.append(f"- ISD: {fmt_float(r.get('isd_v11', 0))}")
            linhas.append("")
    return "\n".join(linhas)


# -----------------------------
# Carregamento
# -----------------------------
st.set_page_config(
    layout="wide",
    page_title="Dashboard Master Bruna — V12",
    page_icon="🧭",
)

geojson = tentar_json(GEOJSON_FILE)

df_v9 = tentar_csv(BASE_V9)
df_v10 = tentar_csv(BASE_V10)
df_consolidado = consolidar_v9_v10(df_v9, df_v10)

# V6/V3 mapa executivo: tenta várias bases para não quebrar.
base_ia_path = escolher_base_existente([BASE_V6_POLITICO, BASE_V6_REAL_ALT, BASE_V3_IA, BASE_V5, BASE_V4, BASE_V3_REAL])
df_ia = tentar_csv(base_ia_path) if base_ia_path else pd.DataFrame()
df_ia = normalizar_coluna_municipio(df_ia)

metricas_v6 = tentar_json(METRICAS_V6)
metricas_ia = tentar_json(METRICAS_IA)
importancias_ia = tentar_csv(IMPORTANCIAS_IA)

df_mencoes, df_digital_mun = carregar_bases_digitais()

if not df_consolidado.empty and geojson:
    df_consolidado = preparar_mapa_generico(df_consolidado, geojson, "CIDADE")

if not df_ia.empty and geojson:
    df_ia = preparar_mapa_generico(df_ia, geojson, "CIDADE")

if not df_digital_mun.empty and geojson:
    df_digital_mun = preparar_mapa_generico(df_digital_mun, geojson, "CIDADE")

df_master = integrar_digital(df_consolidado, df_digital_mun)
if not df_master.empty and geojson:
    df_master = preparar_mapa_generico(df_master, geojson, "CIDADE")

if df_master.empty and not df_ia.empty:
    df_master = df_ia.copy()


# -----------------------------
# Interface
# -----------------------------
st.title("Dashboard Master da Campanha — Bruna V12")
st.caption("V6 Executivo + V9 Clusters + V10 Agenda + V11 Digital + Relatórios + Mapa Estratégico.")

with st.expander("Como ler este dashboard master"):
    st.markdown(
        """
        Este painel reúne todas as camadas anteriores sem excluir funcionalidades:

        - **V6 Executivo/IA:** leitura de previsão, cenários e mapa por score híbrido.
        - **V9 Clusters:** sustentação, expansão quente, presença estratégica e custo alto.
        - **V10 Agenda:** priorização prática de presença política.
        - **V11 Digital:** sentimento público observável, rejeição digital e temas.
        - **V12 Master:** soma a leitura territorial com a camada digital, quando os arquivos digitais estão disponíveis.

        Observação: a camada digital usa dados públicos indexados e não substitui pesquisa eleitoral.
        """
    )

if not geojson:
    st.warning("Arquivo ma_municipios.geojson não encontrado. As abas de mapa serão exibidas parcialmente ou ficarão indisponíveis.")

# Sidebar
st.sidebar.header("Filtros gerais")

df_filtro_base = df_master.copy() if not df_master.empty else pd.DataFrame()

if not df_filtro_base.empty:
    if "cluster_v9" in df_filtro_base.columns:
        clusters = sorted([str(c) for c in df_filtro_base["cluster_v9"].dropna().unique()])
        cluster_sel = st.sidebar.multiselect("Cluster estratégico", clusters, default=clusters)
        df_filtro_base = df_filtro_base[df_filtro_base["cluster_v9"].astype(str).isin(cluster_sel)]

    if "prioridade_agenda" in df_filtro_base.columns:
        agendas = sorted([str(a) for a in df_filtro_base["prioridade_agenda"].dropna().unique()])
        agenda_sel = st.sidebar.multiselect("Prioridade de agenda", agendas, default=agendas)
        df_filtro_base = df_filtro_base[df_filtro_base["prioridade_agenda"].astype(str).isin(agenda_sel)]

    busca = st.sidebar.text_input("Buscar município")
    if busca and "CIDADE" in df_filtro_base.columns:
        df_filtro_base = df_filtro_base[
            df_filtro_base["CIDADE"].astype(str).str.contains(busca, case=False, na=False)
        ]

df_filtrado = df_filtro_base.copy()

# KPIs
if not df_filtrado.empty:
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Municípios", fmt_int(len(df_filtrado)))
    if "expectativa_total" in df_filtrado.columns:
        k2.metric("Meta total", fmt_int(df_filtrado["expectativa_total"].sum()))
    else:
        k2.metric("Meta total", "0")
    k3.metric("Agenda imediata", fmt_int((df_filtrado.get("prioridade_agenda", pd.Series(dtype=str)) == "Agenda imediata").sum()))
    k4.metric("Expansão quente", fmt_int((df_filtrado.get("cluster_v9", pd.Series(dtype=str)) == "Expansão quente").sum()))
    if "indice_consolidado" in df_filtrado.columns:
        k5.metric("Índice consolidado", fmt_float(df_filtrado["indice_consolidado"].mean()))
    else:
        k5.metric("Índice consolidado", "0")
    if "isd_v11" in df_filtrado.columns:
        k6.metric("ISD médio", fmt_float(df_filtrado["isd_v11"].replace(0, pd.NA).dropna().mean() if len(df_filtrado) else 0))
    else:
        k6.metric("ISD médio", "0")
else:
    st.warning("Nenhuma base principal foi carregada. Verifique se os CSVs estão na mesma pasta do dashboard.")

# Cenários IA, quando houver
metricas_exibir = metricas_v6 or metricas_ia
if metricas_exibir:
    st.markdown("### Cenários IA")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Meta original", fmt_int(metricas_exibir.get("meta_total", 0)))
    c2.metric("Conservador", fmt_int(metricas_exibir.get("cenario_conservador", 0)))
    c3.metric("Realista IA", fmt_int(metricas_exibir.get("cenario_realista", metricas_exibir.get("previsao_total", 0))))
    c4.metric("Forte", fmt_int(metricas_exibir.get("cenario_forte", 0)))

st.divider()

# Município selecionado
if not df_filtrado.empty and "CIDADE" in df_filtrado.columns:
    municipio = st.selectbox(
        "Escolha um município para análise detalhada",
        sorted(df_filtrado["CIDADE"].dropna().unique().tolist()),
    )
    linha = df_filtrado[df_filtrado["CIDADE"] == municipio].iloc[0]

    st.subheader(f"Resumo estratégico — {municipio}")
    st.info(
        f"""
**Cluster V9:** {linha.get('cluster_v9', 'Não informado')}  
**Prioridade V8:** {linha.get('prioridade_v8', 'Não informado')}  
**Prioridade de agenda V10:** {linha.get('prioridade_agenda', 'Não informado')}  
**Ação recomendada:** {linha.get('acao_recomendada', 'Não informado')}  
**Leitura digital:** {linha.get('classificacao_isd', 'Sem dados digitais')}
"""
    )

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Meta local", fmt_int(linha.get("expectativa_total", linha.get("expectativa", 0))))
    m2.metric("Score político", fmt_float(linha.get("score_municipal_v8", linha.get("score_final_v6", 0))))
    m3.metric("Agenda score", fmt_float(linha.get("agenda_score", 0)))
    m4.metric("Eficiência (%)", fmt_float(linha.get("eficiencia_eleitoral", linha.get("penetracao_real_pct", 0))))
    m5.metric("Índice consolidado", fmt_float(linha.get("indice_consolidado", 0)))
    m6.metric("ISD digital", fmt_float(linha.get("isd_v11", 0)))

    if any(c in df_filtrado.columns for c in ["base_eleitoral_v8", "total_liderancas", "peso_medio_liderancas", "forca_media_local", "score_maximo"]):
        l1, l2, l3, l4, l5 = st.columns(5)
        l1.metric("Base eleitoral", fmt_int(linha.get("base_eleitoral_v8", 0)))
        l2.metric("Lideranças", fmt_int(linha.get("total_liderancas", linha.get("qtd_liderancas", 0))))
        l3.metric("Peso médio", fmt_float(linha.get("peso_medio_liderancas", 0)))
        l4.metric("Força local", fmt_float(linha.get("forca_media_local", 0)))
        l5.metric("Score máximo", fmt_float(linha.get("score_maximo", 0)))

st.divider()

tabs = st.tabs([
    "Prioridade Master V12",
    "V6 Executivo IA",
    "Clusters V9",
    "Agenda V10",
    "Mapa Estratégico",
    "Inteligência Digital",
    "Relatórios",
    "Base Completa",
])

# -----------------------------
# Aba 1 — Master
# -----------------------------
with tabs[0]:
    st.subheader("Ranking Master V12")
    if df_filtrado.empty:
        st.warning("Base master não carregada.")
    else:
        ordem = "indice_master_v12" if "indice_master_v12" in df_filtrado.columns else "indice_consolidado"
        if ordem not in df_filtrado.columns:
            ordem = primeira_coluna(df_filtrado, ["score_hibrido_v4", "score_hibrido_v6", "score_municipal_v8", "agenda_score"]) or df_filtrado.columns[0]

        top = df_filtrado.sort_values(ordem, ascending=False).head(30)

        fig = px.bar(
            top,
            x="CIDADE",
            y=ordem,
            color="prioridade_agenda" if "prioridade_agenda" in top.columns else None,
            color_discrete_map=CORES_AGENDA,
            hover_data=[c for c in [
                "cluster_v9", "expectativa_total", "agenda_score", "score_municipal_v8",
                "eficiencia_eleitoral", "isd_v11", "classificacao_isd", "acao_recomendada"
            ] if c in top.columns],
            title="Top 30 municípios por prioridade master",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(top, use_container_width=True, height=520)

# -----------------------------
# Aba 2 — V6 IA
# -----------------------------
with tabs[1]:
    st.subheader("V6 Executivo / Modelo IA")
    if df_ia.empty:
        st.warning("Nenhuma base IA encontrada. Arquivos aceitos: base_modelo_bruna_v6_politico.csv, base_modelo_v6_politico_real.csv, base_modelo_bruna_v3_ia.csv, base_modelo_bruna_v5_recalibrada.csv.")
    else:
        st.caption(f"Base IA carregada: {base_ia_path}")

        col_mun = "CIDADE"
        col_expect = primeira_coluna(df_ia, ["expectativa_ia_v6", "expectativa_ia", "expectativa_total", "expectativa"])
        col_score = primeira_coluna(df_ia, ["score_hibrido_v6", "score_hibrido_v4", "score_final_v6", "score_final_v3", "score_municipal_v8"])
        col_prio = primeira_coluna(df_ia, ["prioridade_ia", "prioridade_v8", "prioridade_agenda"])

        c1, c2, c3, c4 = st.columns(4)
        if col_expect:
            c1.metric("Previsão/Meta total", fmt_int(pd.to_numeric(df_ia[col_expect], errors="coerce").fillna(0).sum()))
        c2.metric("Municípios IA", fmt_int(len(df_ia)))
        if col_score:
            c3.metric("Score médio", fmt_float(pd.to_numeric(df_ia[col_score], errors="coerce").fillna(0).mean()))
        if "qtd_liderancas" in df_ia.columns:
            c4.metric("Lideranças", fmt_int(pd.to_numeric(df_ia["qtd_liderancas"], errors="coerce").fillna(0).sum()))

        if col_score:
            top_ia = df_ia.sort_values(col_score, ascending=False).head(25)
            fig_ia = px.bar(
                top_ia,
                x=col_mun,
                y=col_score,
                color=col_prio if col_prio else None,
                hover_data=[c for c in ["expectativa", "expectativa_ia", "expectativa_ia_v6", "penetracao_real_pct", "qtd_liderancas", "soma_votos_liderancas"] if c in top_ia.columns],
                title=f"Top municípios por {col_score}",
            )
            st.plotly_chart(fig_ia, use_container_width=True)

        if geojson and "mapa_ok" in df_ia.columns and col_score:
            mapa_ia = df_ia[df_ia["mapa_ok"]].copy()
            if not mapa_ia.empty:
                fig_map_ia = px.choropleth_mapbox(
                    mapa_ia,
                    geojson=geojson,
                    locations="cd_mun",
                    featureidkey="properties.CD_MUN",
                    color=col_score,
                    hover_name=col_mun,
                    hover_data={c: True for c in [col_expect, col_prio, col_score] if c},
                    mapbox_style="open-street-map",
                    center={"lat": -5.2, "lon": -45.3},
                    zoom=5.1,
                    opacity=0.65,
                    height=700,
                    title=f"Mapa IA por {col_score}",
                )
                st.plotly_chart(fig_map_ia, use_container_width=True)

        if not importancias_ia.empty:
            st.markdown("#### Importância das variáveis IA")
            xcol = primeira_coluna(importancias_ia, ["importancia", "importance"])
            ycol = primeira_coluna(importancias_ia, ["variavel", "feature"])
            if xcol and ycol:
                fig_imp = px.bar(
                    importancias_ia.head(20).sort_values(xcol),
                    x=xcol,
                    y=ycol,
                    orientation="h",
                    title="Top variáveis que influenciam a previsão"
                )
                st.plotly_chart(fig_imp, use_container_width=True)
            st.dataframe(importancias_ia, use_container_width=True)

        st.dataframe(df_ia, use_container_width=True, height=500)

# -----------------------------
# Aba 3 — V9
# -----------------------------
with tabs[2]:
    st.subheader("Leitura V9 por clusters")
    if df_filtrado.empty or "cluster_v9" not in df_filtrado.columns:
        st.warning("Base V9 não disponível.")
    else:
        fig_cluster = px.histogram(
            df_filtrado,
            x="cluster_v9",
            color="cluster_v9",
            color_discrete_map=CORES_CLUSTER,
            title="Distribuição de municípios por cluster estratégico",
        )
        st.plotly_chart(fig_cluster, use_container_width=True)

        top_v9 = df_filtrado.sort_values(
            [c for c in ["score_municipal_v8", "eficiencia_eleitoral"] if c in df_filtrado.columns],
            ascending=False
        ).head(25)

        y = primeira_coluna(top_v9, ["score_municipal_v8", "indice_consolidado", "agenda_score"])
        if y:
            fig_v9 = px.bar(
                top_v9,
                x="CIDADE",
                y=y,
                color="cluster_v9",
                color_discrete_map=CORES_CLUSTER,
                hover_data=[c for c in ["expectativa_total", "eficiencia_eleitoral", "acao_recomendada"] if c in top_v9.columns],
                title=f"Top 25 municípios por {y}",
            )
            st.plotly_chart(fig_v9, use_container_width=True)

# -----------------------------
# Aba 4 — V10 Agenda
# -----------------------------
with tabs[3]:
    st.subheader("Leitura V10 de agenda")
    if df_filtrado.empty or "prioridade_agenda" not in df_filtrado.columns:
        st.warning("Base V10 não disponível.")
    else:
        fig_agenda_dist = px.histogram(
            df_filtrado,
            x="prioridade_agenda",
            color="prioridade_agenda",
            color_discrete_map=CORES_AGENDA,
            title="Distribuição por prioridade de agenda",
        )
        st.plotly_chart(fig_agenda_dist, use_container_width=True)

        top_agenda = df_filtrado.sort_values("agenda_score", ascending=False).head(25)
        fig_agenda = px.bar(
            top_agenda,
            x="CIDADE",
            y="agenda_score",
            color="prioridade_agenda",
            color_discrete_map=CORES_AGENDA,
            hover_data=[c for c in ["cluster_v9", "expectativa_total", "eficiencia_eleitoral", "acao_recomendada"] if c in top_agenda.columns],
            title="Top 25 municípios para agenda",
        )
        st.plotly_chart(fig_agenda, use_container_width=True)

# -----------------------------
# Aba 5 — Mapa Estratégico
# -----------------------------
with tabs[4]:
    st.subheader("Mapa estratégico com múltiplas camadas")
    if not geojson:
        st.warning("GeoJSON não encontrado.")
    elif df_filtrado.empty or "mapa_ok" not in df_filtrado.columns:
        st.warning("Base sem correspondência de mapa.")
    else:
        mapa_df = df_filtrado[df_filtrado["mapa_ok"]].copy()
        if mapa_df.empty:
            st.warning("Nenhum município casado com o GeoJSON.")
        else:
            opcoes_mapa = []
            if "prioridade_agenda" in mapa_df.columns:
                opcoes_mapa.append("Prioridade de agenda")
            if "cluster_v9" in mapa_df.columns:
                opcoes_mapa.append("Cluster estratégico")
            if "indice_consolidado" in mapa_df.columns:
                opcoes_mapa.append("Índice consolidado")
            if "indice_master_v12" in mapa_df.columns:
                opcoes_mapa.append("Índice Master V12")
            if "isd_v11" in mapa_df.columns:
                opcoes_mapa.append("ISD Digital")
            score_ia_map = primeira_coluna(mapa_df, ["score_hibrido_v6", "score_hibrido_v4", "score_final_v6", "score_final_v3"])
            if score_ia_map:
                opcoes_mapa.append("Score IA")

            modo_mapa = st.radio("Colorir mapa por", opcoes_mapa, horizontal=True)

            if modo_mapa == "Prioridade de agenda":
                color = "prioridade_agenda"
                kwargs = {"color_discrete_map": CORES_AGENDA}
            elif modo_mapa == "Cluster estratégico":
                color = "cluster_v9"
                kwargs = {"color_discrete_map": CORES_CLUSTER}
            elif modo_mapa == "ISD Digital":
                color = "isd_v11"
                kwargs = {}
            elif modo_mapa == "Índice Master V12":
                color = "indice_master_v12"
                kwargs = {}
            elif modo_mapa == "Score IA":
                color = score_ia_map
                kwargs = {}
            else:
                color = "indice_consolidado"
                kwargs = {}

            fig_map = px.choropleth_mapbox(
                mapa_df,
                geojson=geojson,
                locations="cd_mun",
                featureidkey="properties.CD_MUN",
                color=color,
                hover_name="CIDADE",
                hover_data={c: True for c in [
                    "cluster_v9", "prioridade_agenda", "agenda_score", "score_municipal_v8",
                    "expectativa_total", "indice_consolidado", "indice_master_v12", "isd_v11",
                    "classificacao_isd"
                ] if c in mapa_df.columns},
                mapbox_style="open-street-map",
                center={"lat": -5.2, "lon": -45.3},
                zoom=5.1,
                opacity=0.70,
                height=760,
                title=f"Mapa por {modo_mapa}",
                **kwargs,
            )
            st.plotly_chart(fig_map, use_container_width=True)

            sem_mapa = df_filtrado[~df_filtrado["mapa_ok"]]
            if not sem_mapa.empty:
                with st.expander("Municípios sem correspondência no mapa"):
                    st.dataframe(sem_mapa[[c for c in ["CIDADE", "cidade_norm"] if c in sem_mapa.columns]], use_container_width=True)

# -----------------------------
# Aba 6 — Digital
# -----------------------------
with tabs[5]:
    st.subheader("Inteligência Digital — ISD V11")
    if df_mencoes.empty or df_digital_mun.empty:
        st.warning("Base digital não encontrada. Coloque base_sentimento_bruna_v11_seed_publica.csv ou base_sentimento_bruna_v11_classificada.csv na pasta.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Menções públicas", fmt_int(len(df_mencoes)))
        c2.metric("Municípios citados", fmt_int(df_digital_mun["CIDADE"].nunique()))
        c3.metric("ISD médio", fmt_float(df_digital_mun["isd_v11"].mean() if "isd_v11" in df_digital_mun.columns else 0))
        c4.metric("Rejeição média", fmt_float(df_digital_mun["rejeicao_media"].mean() if "rejeicao_media" in df_digital_mun.columns else 0))

        fig_dig = px.bar(
            df_digital_mun.sort_values("isd_v11", ascending=False),
            x="CIDADE",
            y="isd_v11",
            color="classificacao_isd" if "classificacao_isd" in df_digital_mun.columns else None,
            hover_data=[c for c in ["qtd_mencoes", "sentimento_medio", "rejeicao_media", "fontes"] if c in df_digital_mun.columns],
            title="ISD por município"
        )
        st.plotly_chart(fig_dig, use_container_width=True)

        if "fonte" in df_mencoes.columns and "sentimento_label" in df_mencoes.columns:
            fig_fontes = px.histogram(
                df_mencoes,
                x="fonte",
                color="sentimento_label",
                title="Menções por fonte e sentimento"
            )
            st.plotly_chart(fig_fontes, use_container_width=True)

        if "temas" in df_mencoes.columns:
            temas = []
            for t in df_mencoes["temas"].dropna():
                temas.extend([x.strip() for x in str(t).split(";") if x.strip()])
            if temas:
                temas_df = pd.DataFrame({"tema": temas})
                temas_count = temas_df.value_counts("tema").reset_index(name="qtd").sort_values("qtd", ascending=False)
                fig_temas = px.bar(temas_count.head(25), x="tema", y="qtd", title="Temas dominantes")
                st.plotly_chart(fig_temas, use_container_width=True)
                st.dataframe(temas_count, use_container_width=True)

        st.markdown("#### Base auditável digital")
        st.dataframe(df_mencoes, use_container_width=True, height=500)

# -----------------------------
# Aba 7 — Relatórios
# -----------------------------
with tabs[6]:
    st.subheader("Relatórios de fácil compreensão")
    st.markdown(resumo_executivo_digital(df_digital_mun, df_mencoes))

    st.divider()
    st.markdown("### Como interpretar os índices")
    with st.expander("O que é ISD?"):
        st.write(
            """
            **ISD — Índice de Sentimento Digital** é uma nota de 0 a 100 que resume o ambiente digital público
            de cada município. Ele combina sentimento, engajamento estimado, alcance territorial e rejeição.
            Quanto maior o ISD, mais favorável é o ambiente digital observado.
            """
        )
    with st.expander("O que é o Índice Master V12?"):
        st.write(
            """
            O **Índice Master V12** combina a prioridade territorial/política do dashboard consolidado com a camada
            de sentimento digital. Quando não há dados digitais para um município, a leitura territorial continua válida,
            mas a camada digital precisa ser ampliada.
            """
        )
    with st.expander("Atenção metodológica"):
        st.write(
            """
            A camada digital mede presença e sentimento em fontes abertas. Ela não substitui pesquisa quantitativa,
            qualitativa ou tracking eleitoral.
            """
        )

    if not df_filtrado.empty and "CIDADE" in df_filtrado.columns:
        st.markdown("### Relatório por município")
        municipio_rel = st.selectbox(
            "Escolha o município para relatório automático",
            sorted(df_filtrado["CIDADE"].dropna().unique().tolist()),
            key="municipio_relatorio_v12"
        )
        row_rel = df_filtrado[df_filtrado["CIDADE"] == municipio_rel].iloc[0]
        st.info(interpretar_municipio_digital(row_rel))

        st.markdown("### Leitura territorial")
        st.success(
            f"""
**{municipio_rel}** está no cluster **{row_rel.get('cluster_v9', 'não informado')}**, 
com prioridade de agenda **{row_rel.get('prioridade_agenda', 'não informada')}**.  
Ação recomendada: **{row_rel.get('acao_recomendada', 'não informada')}**.
"""
        )

    relatorio = gerar_relatorio_master(df_filtrado, df_digital_mun, df_mencoes)
    st.download_button(
        "Baixar relatório master em Markdown",
        data=relatorio,
        file_name="relatorio_master_bruna_v12.md",
        mime="text/markdown"
    )

# -----------------------------
# Aba 8 — Base
# -----------------------------
with tabs[7]:
    st.subheader("Base completa consolidada")
    if not df_filtrado.empty:
        st.dataframe(df_filtrado, use_container_width=True, height=680)
        csv = df_filtrado.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Baixar base master filtrada CSV",
            data=csv,
            file_name="base_master_bruna_v12.csv",
            mime="text/csv",
        )
    else:
        st.warning("Nenhuma base consolidada disponível.")
