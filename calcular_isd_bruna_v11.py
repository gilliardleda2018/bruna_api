
import pandas as pd
from pathlib import Path

INPUT = "base_sentimento_bruna_v11_seed_publica.csv"
OUTPUT_MENCOES = "base_sentimento_bruna_v11_classificada.csv"
OUTPUT_MUNICIPIOS = "isd_municipios_bruna_v11.csv"

def normalizar_0_100(s):
    s = pd.to_numeric(s, errors="coerce").fillna(0)
    if s.max() == s.min():
        return pd.Series([50] * len(s), index=s.index)
    return ((s - s.min()) / (s.max() - s.min()) * 100).clip(0, 100)

def label_to_score(label):
    label = str(label).lower().strip()
    if label == "positivo":
        return 75
    if label == "negativo":
        return 25
    return 50

def calcular_isd_linha(row):
    sentimento = row.get("sentimento_score", label_to_score(row.get("sentimento_label", "neutro")))
    engajamento = row.get("engajamento_publico_est", 50)
    alcance = row.get("alcance_territorial_est", 50)
    rejeicao = row.get("rejeicao_est", 25)
    # Fórmula auditável, 0-100
    return max(0, min(100, 
        0.40 * sentimento +
        0.25 * engajamento +
        0.25 * alcance -
        0.10 * rejeicao
    ))

def main():
    df = pd.read_csv(INPUT)

    for col in ["sentimento_score", "engajamento_publico_est", "alcance_territorial_est", "rejeicao_est"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["sentimento_score"] = df["sentimento_score"].fillna(df["sentimento_label"].apply(label_to_score))
    df["engajamento_publico_est"] = df["engajamento_publico_est"].fillna(50)
    df["alcance_territorial_est"] = df["alcance_territorial_est"].fillna(50)
    df["rejeicao_est"] = df["rejeicao_est"].fillna(25)

    df["isd_mencao"] = df.apply(calcular_isd_linha, axis=1).round(2)

    # Agregação municipal
    mun = (
        df.groupby("municipio", dropna=False)
        .agg(
            qtd_mencoes=("id_mencao", "count"),
            sentimento_medio=("sentimento_score", "mean"),
            engajamento_medio=("engajamento_publico_est", "mean"),
            alcance_medio=("alcance_territorial_est", "mean"),
            rejeicao_media=("rejeicao_est", "mean"),
            isd_medio=("isd_mencao", "mean"),
            fontes=("fonte", lambda x: "; ".join(sorted(set(map(str, x))))),
            temas=("temas", lambda x: "; ".join(sorted(set(";".join(map(str, x)).split(";")))))
        )
        .reset_index()
    )

    # Volume normalizado de menções entra como pequena correção no índice final
    mun["volume_mencoes_score"] = normalizar_0_100(mun["qtd_mencoes"])
    mun["isd_v11"] = (
        0.85 * mun["isd_medio"] +
        0.15 * mun["volume_mencoes_score"]
    ).round(2)

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

    mun["classificacao_isd"] = mun["isd_v11"].apply(classificar)

    df.to_csv(OUTPUT_MENCOES, index=False, encoding="utf-8-sig")
    mun.sort_values("isd_v11", ascending=False).to_csv(OUTPUT_MUNICIPIOS, index=False, encoding="utf-8-sig")

    print("Arquivos gerados:")
    print(f"- {OUTPUT_MENCOES}")
    print(f"- {OUTPUT_MUNICIPIOS}")

if __name__ == "__main__":
    main()
