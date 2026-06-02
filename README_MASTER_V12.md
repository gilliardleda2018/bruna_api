
# Dashboard Master Bruna V12

Este dashboard mescla as funcionalidades dos painéis enviados:

- V6 Executivo com mapa e IA;
- V9 Executivo / clusters;
- V10 Agenda estratégica;
- V11 Consolidado;
- V11 Inteligência Digital e relatórios explicativos;
- Nova aba de mapa estratégico com múltiplas camadas.

## Arquivos que podem ser usados na mesma pasta

Obrigatórios para a visão consolidada completa:

- `municipios_consolidados_v9_cluster.csv`
- `agenda_v10_campanha.csv`
- `ma_municipios.geojson`

Opcionais:

- `base_modelo_bruna_v6_politico.csv`
- `base_modelo_v6_politico_real.csv`
- `base_modelo_bruna_v3_ia.csv`
- `base_modelo_bruna_v5_recalibrada.csv`
- `metricas_modelo_ia_v6.json`
- `metricas_modelo_ia.json`
- `importancias_modelo_ia.csv`
- `base_sentimento_bruna_v11_seed_publica.csv`
- `base_sentimento_bruna_v11_classificada.csv`
- `isd_municipios_bruna_v11.csv`

## Como executar

```bash
pip install -r requirements_master_v12.txt
python -m streamlit run dashboard_bruna_master_v12.py
```

## Observação

O dashboard não exclui as funcionalidades anteriores. Ele acrescenta novas abas e tenta carregar os arquivos disponíveis sem quebrar a execução.
