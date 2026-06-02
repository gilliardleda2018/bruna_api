from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="API Atlas Bruna Pessoa V12",
    description="API pública para servir dados consolidados do Dashboard Bruna Master V12.",
    version="1.0.0",
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

def carregar_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

def normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.where(pd.notnull(df), None)

@app.get("/")
def home():
    return {
        "status": "online",
        "projeto": "Atlas Bruna Pessoa V12",
        "endpoints": [
            "/api/resumo",
            "/api/municipios",
            "/api/municipio/{nome}",
            "/api/ranking",
            "/api/digital",
            "/api/mencoes",
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

    meta = pd.to_numeric(df.get("expectativa_total", 0), errors="coerce").fillna(0)
    indice = pd.to_numeric(df.get("indice_consolidado", 0), errors="coerce").fillna(0)
    master = pd.to_numeric(df.get("indice_master_v12", 0), errors="coerce").fillna(0)

    isd_medio = None
    if not dig.empty and "isd_v11" in dig.columns:
        isd_medio = float(pd.to_numeric(dig["isd_v11"], errors="coerce").fillna(0).mean())

    return {
        "status": "ok",
        "municipios": int(len(df)),
        "meta_total": round(float(meta.sum()), 2),
        "indice_consolidado_medio": round(float(indice.mean()), 2),
        "indice_master_v12_medio": round(float(master.mean()), 2),
        "isd_medio": round(isd_medio, 2) if isd_medio is not None else None,
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

    return normalizar_df(df).to_dict(orient="records")

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

    return {"status": "ok", "dados": normalizar_df(filtro).iloc[0].to_dict()}

@app.get("/api/ranking")
def ranking(indicador: str = Query("indice_master_v12"), limite: int = Query(20, ge=1, le=200)):
    df = carregar_csv(BASE_MASTER)
    if df.empty:
        return []

    if indicador not in df.columns:
        indicador = "indice_consolidado" if "indice_consolidado" in df.columns else df.columns[0]

    df[indicador] = pd.to_numeric(df[indicador], errors="coerce").fillna(0)
    out = df.sort_values(indicador, ascending=False).head(limite)
    return normalizar_df(out).to_dict(orient="records")

@app.get("/api/digital")
def digital():
    dig = carregar_csv(BASE_DIGITAL)
    if dig.empty:
        return []
    return normalizar_df(dig).to_dict(orient="records")

@app.get("/api/mencoes")
def mencoes(limite: int = Query(100, ge=1, le=1000)):
    df = carregar_csv(BASE_MENCOES)
    if df.empty:
        return []
    return normalizar_df(df.head(limite)).to_dict(orient="records")