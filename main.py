from pathlib import Path
from typing import Optional
import json
import math

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="API Atlas Bruna Pessoa V12",
    description="API pública para servir dados consolidados, digitais e mapa do Dashboard Bruna Master V12.",
    version="2.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_MASTER = Path("base_master_bruna_v12.csv")
BASE_DIGITAL = Path("isd_municipios_bruna_v11.csv")
BASE_MENCOES = Path("base_sentimento_bruna_v11_classificada.csv")
GEOJSON_FILE = Path("ma_municipios.geojson")


def carregar_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def safe_value(v):
    if v is None:
        return None

    try:
        if pd.isna(v):
            return None
    except Exception:
        pass

    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v

    if hasattr(v, "item"):
        try:
            return safe_value(v.item())
        except Exception:
            return str(v)

    return v


def safe_records(df: pd.DataFrame):
    if df.empty:
        return []

    df = df.copy()
    df = df.replace([float("inf"), float("-inf")], None)
    df = df.astype(object).where(pd.notnull(df), None)

    registros = df.to_dict(orient="records")

    return [
        {str(k): safe_value(v) for k, v in row.items()}
        for row in registros
    ]


def safe_one(df: pd.DataFrame):
    registros = safe_records(df)
    return registros[0] if registros else None


def serie_numerica(df: pd.DataFrame, coluna: str, default=0):
    if coluna in df.columns:
        return pd.to_numeric(df[coluna], errors="coerce").fillna(default)
    return pd.Series([default] * len(df))


@app.get("/")
def home():
    return {
        "status": "online",
        "projeto": "Atlas Bruna Pessoa V12",
        "versao": "2.0.1",
        "endpoints": [
            "/api/resumo",
            "/api/filtros",
            "/api/municipios",
            "/api/municipio/{nome}",
            "/api/ranking",
            "/api/digital",
            "/api/mencoes",
            "/api/geojson",
            "/api/mapa",
        ],
    }


@app.get("/api/resumo")
def resumo():
    df = carregar_csv(BASE_MASTER)
    dig = carregar_csv(BASE_DIGITAL)

    if df.empty:
        return {
            "status": "sem_base",
            "mensagem": "Arquivo base_master_bruna_v12.csv não encontrado na pasta da API.",
        }

    meta = serie_numerica(df, "expectativa_total")
    indice = serie_numerica(df, "indice_consolidado")
    master = serie_numerica(df, "indice_master_v12")

    agenda_imediata = (
        int((df["prioridade_agenda"].astype(str) == "Agenda imediata").sum())
        if "prioridade_agenda" in df.columns
        else 0
    )

    expansao = (
        int((df["cluster_v9"].astype(str) == "Expansão quente").sum())
        if "cluster_v9" in df.columns
        else 0
    )

    isd_medio = None

    if not dig.empty and "isd_v11" in dig.columns:
        isd = pd.to_numeric(dig["isd_v11"], errors="coerce").replace([float("inf"), float("-inf")], pd.NA).dropna()
        isd_medio = float(isd.mean()) if not isd.empty else None
    elif "isd_v11" in df.columns:
        isd = pd.to_numeric(df["isd_v11"], errors="coerce").replace([float("inf"), float("-inf")], pd.NA).dropna()
        isd = isd[isd != 0]
        isd_medio = float(isd.mean()) if not isd.empty else None

    return {
        "status": "ok",
        "municipios": int(len(df)),
        "meta_total": round(float(meta.sum()), 2),
        "agenda_imediata": agenda_imediata,
        "expansao_quente": expansao,
        "indice_consolidado_medio": round(float(indice.mean()), 2),
        "indice_master_v12_medio": round(float(master.mean()), 2),
        "isd_medio": round(isd_medio, 2) if isd_medio is not None else None,
    }


@app.get("/api/filtros")
def filtros():
    df = carregar_csv(BASE_MASTER)

    if df.empty:
        return {"clusters": [], "agendas": [], "municipios": []}

    return {
        "clusters": sorted(df["cluster_v9"].dropna().astype(str).unique().tolist()) if "cluster_v9" in df.columns else [],
        "agendas": sorted(df["prioridade_agenda"].dropna().astype(str).unique().tolist()) if "prioridade_agenda" in df.columns else [],
        "municipios": sorted(df["CIDADE"].dropna().astype(str).unique().tolist()) if "CIDADE" in df.columns else [],
    }


@app.get("/api/municipios")
def municipios(
    cluster: Optional[str] = Query(None),
    agenda: Optional[str] = Query(None),
    busca: Optional[str] = Query(None),
):
    df = carregar_csv(BASE_MASTER)

    if df.empty:
        return []

    if cluster and "cluster_v9" in df.columns:
        df = df[df["cluster_v9"].astype(str).str.lower() == cluster.lower()]

    if agenda and "prioridade_agenda" in df.columns:
        df = df[df["prioridade_agenda"].astype(str).str.lower() == agenda.lower()]

    if busca and "CIDADE" in df.columns:
        df = df[df["CIDADE"].astype(str).str.contains(busca, case=False, na=False)]

    return safe_records(df)


@app.get("/api/municipio/{nome}")
def municipio(nome: str):
    df = carregar_csv(BASE_MASTER)

    if df.empty or "CIDADE" not in df.columns:
        return {"status": "nao_encontrado"}

    filtro = df[df["CIDADE"].astype(str).str.lower() == nome.lower()]

    if filtro.empty:
        filtro = df[df["CIDADE"].astype(str).str.contains(nome, case=False, na=False)]

    if filtro.empty:
        return {"status": "nao_encontrado", "municipio": nome}

    return {"status": "ok", "dados": safe_one(filtro)}


@app.get("/api/ranking")
def ranking(
    indicador: str = Query("indice_master_v12"),
    limite: int = Query(30, ge=1, le=500),
    cluster: Optional[str] = Query(None),
    agenda: Optional[str] = Query(None),
):
    df = carregar_csv(BASE_MASTER)

    if df.empty:
        return []

    if cluster and "cluster_v9" in df.columns:
        df = df[df["cluster_v9"].astype(str).str.lower() == cluster.lower()]

    if agenda and "prioridade_agenda" in df.columns:
        df = df[df["prioridade_agenda"].astype(str).str.lower() == agenda.lower()]

    if df.empty:
        return []

    if indicador not in df.columns:
        indicador = "indice_consolidado" if "indice_consolidado" in df.columns else df.columns[0]

    df = df.copy()
    df[indicador] = pd.to_numeric(df[indicador], errors="coerce").fillna(0)

    out = df.sort_values(indicador, ascending=False).head(limite)

    return safe_records(out)


@app.get("/api/digital")
def digital():
    dig = carregar_csv(BASE_DIGITAL)

    if dig.empty:
        df = carregar_csv(BASE_MASTER)

        if df.empty:
            return []

        cols = [
            "CIDADE",
            "qtd_mencoes",
            "sentimento_medio",
            "engajamento_medio",
            "alcance_medio",
            "rejeicao_media",
            "isd_v11",
            "classificacao_isd",
            "fontes",
            "temas",
        ]

        cols = [c for c in cols if c in df.columns]

        if not cols:
            return []

        dig = df[cols].copy()

    return safe_records(dig)


@app.get("/api/mencoes")
def mencoes(limite: int = Query(200, ge=1, le=2000)):
    df = carregar_csv(BASE_MENCOES)

    if df.empty:
        return []

    return safe_records(df.head(limite))


@app.get("/api/geojson")
def geojson():
    if not GEOJSON_FILE.exists():
        return {
            "status": "sem_geojson",
            "mensagem": "Arquivo ma_municipios.geojson não encontrado.",
        }

    with open(GEOJSON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/mapa")
def mapa(indicador: str = Query("indice_master_v12")):
    df = carregar_csv(BASE_MASTER)

    if df.empty:
        return {"status": "sem_base", "dados": []}

    if indicador not in df.columns:
        if "indice_consolidado" in df.columns:
            indicador = "indice_consolidado"
        else:
            indicador = None

    campos = [
        "CIDADE",
        "cd_mun",
        "cluster_v9",
        "prioridade_agenda",
        "expectativa_total",
        "agenda_score",
        "score_municipal_v8",
        "eficiencia_eleitoral",
        "indice_consolidado",
        "indice_master_v12",
        "isd_v11",
        "classificacao_isd",
        "acao_recomendada",
    ]

    campos_existentes = [c for c in campos if c in df.columns]

    if not campos_existentes:
        return {"status": "sem_campos", "indicador": indicador, "dados": []}

    out = df[campos_existentes].copy()

    for col in out.columns:
        if col not in [
            "CIDADE",
            "cluster_v9",
            "prioridade_agenda",
            "classificacao_isd",
            "acao_recomendada",
        ]:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    return {
        "status": "ok",
        "indicador": indicador,
        "dados": safe_records(out),
    }
