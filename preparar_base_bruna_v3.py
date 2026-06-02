
import pandas as pd
import numpy as np

INPUT_FILE = "CIDADES ATUALIZADO.xlsx"
OUTPUT_FILE = "base_modelo_bruna_v3_real.csv"

def norm(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0).astype(float)
    mn, mx = s.min(), s.max()
    if mx == mn:
        return pd.Series(50.0, index=s.index)
    return (s - mn) / (mx - mn) * 100

def classe(score: float) -> str:
    if score < 40:
        return "baixa"
    if score < 55:
        return "competitiva"
    if score < 70:
        return "muito competitiva"
    return "zona de eleição"

df = pd.read_excel(INPUT_FILE)

master_cols = [
    "Região - Mapa Politico ", "CIDADE", "VOTO TOTAL", "EXPECTATIVA",
    "CANDIDATO 2022 (DEP EST.)", "VOTOS 2022", "CANDIDATO 2024 (PREF)",
    "VOTOS 2024", "DEP. FEDERAL 2026", "LÍDER REFERÊNCIA"
]
for c in master_cols:
    df[c] = df[c].ffill()

df = df[df["Liderança/Grupo Politico "].notna()].copy()

for c in ["VOTO TOTAL", "EXPECTATIVA", "QUANT. VOTOS TIROU", "VOTOS 2022", "VOTOS 2024", "ANO CANDIDATURA"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

municipal = df.groupby("CIDADE").agg(
    regiao=("Região - Mapa Politico ", lambda s: s.dropna().iloc[0] if s.dropna().size else np.nan),
    voto_total=("VOTO TOTAL", "max"),
    expectativa=("EXPECTATIVA", "max"),
    qtd_liderancas=("Liderança/Grupo Politico ", "count"),
    soma_votos_liderancas=("QUANT. VOTOS TIROU", lambda s: s.fillna(0).sum()),
    media_votos_liderancas=("QUANT. VOTOS TIROU", lambda s: s.fillna(0).mean()),
    max_votos_lideranca=("QUANT. VOTOS TIROU", lambda s: s.fillna(0).max()),
    votos_dep_est_2022=("VOTOS 2022", "max"),
    votos_pref_2024=("VOTOS 2024", "max"),
    dep_est_2022=("CANDIDATO 2022 (DEP EST.)", lambda s: s.dropna().iloc[0] if s.dropna().size else ""),
    pref_2024=("CANDIDATO 2024 (PREF)", lambda s: s.dropna().iloc[0] if s.dropna().size else ""),
    dep_fed_2026=("DEP. FEDERAL 2026", lambda s: s.dropna().iloc[0] if s.dropna().size else ""),
    lider_ref=("LÍDER REFERÊNCIA", lambda s: s.dropna().iloc[0] if s.dropna().size else ""),
).reset_index().rename(columns={"CIDADE": "municipio"})

municipal["expectativa"] = municipal["expectativa"].fillna(0)
municipal["penetracao_real_pct"] = np.where(
    municipal["voto_total"] > 0,
    municipal["expectativa"] / municipal["voto_total"] * 100,
    0
)

municipal["peso_territorial"] = norm(municipal["voto_total"])
municipal["score_base_real"] = 0.60 * norm(municipal["penetracao_real_pct"]) + 0.40 * municipal["peso_territorial"]
municipal["qtd_liderancas_score"] = norm(municipal["qtd_liderancas"])
municipal["soma_votos_liderancas_score"] = norm(municipal["soma_votos_liderancas"])
municipal["score_liderancas"] = 0.50 * municipal["qtd_liderancas_score"] + 0.50 * municipal["soma_votos_liderancas_score"]

# parâmetros globais editáveis do bloco reputacional
sentimento_positivo = 74
sentimento_neutro = 58
coerencia_narrativa = 68
volatilidade_partidaria = 62
municipal["score_sentimento"] = (
    0.40 * sentimento_positivo
    + 0.25 * sentimento_neutro
    + 0.20 * coerencia_narrativa
    + 0.15 * (100 - volatilidade_partidaria)
)

ataques_oposicao = 34
denuncias_publicas = 26
persistencia_tema = 28
municipal["score_risco_ajustado"] = 100 - (
    0.40 * ataques_oposicao
    + 0.35 * denuncias_publicas
    + 0.25 * persistencia_tema
)

municipal["score_final_v3"] = (
    0.35 * municipal["score_base_real"]
    + 0.25 * municipal["score_liderancas"]
    + 0.20 * municipal["score_sentimento"]
    + 0.20 * municipal["score_risco_ajustado"]
)

municipal["classe_competitividade"] = municipal["score_final_v3"].apply(classe)
municipal["votos_conservador"] = np.round(municipal["expectativa"] * np.where(municipal["score_final_v3"] >= 60, 0.90, 0.80)).fillna(0).astype(int)
municipal["votos_realista"] = np.round(municipal["expectativa"] * np.where(municipal["score_final_v3"] >= 60, 1.00, 0.90)).fillna(0).astype(int)
municipal["votos_forte"] = np.round(municipal["expectativa"] * np.where(municipal["score_final_v3"] >= 60, 1.15, 1.00)).fillna(0).astype(int)

municipal = municipal.sort_values(["score_final_v3", "expectativa"], ascending=[False, False]).reset_index(drop=True)
municipal.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
print(f"Arquivo gerado: {OUTPUT_FILE}")
print(municipal.head(15)[["municipio", "expectativa", "penetracao_real_pct", "score_final_v3", "classe_competitividade"]])
