# API Atlas Bruna Pessoa V12

## Rodar localmente

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Acesse:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

## Arquivos de dados esperados na pasta da API

- `base_master_bruna_v12.csv`
- `isd_municipios_bruna_v11.csv`
- `base_sentimento_bruna_v11_classificada.csv`

A base `base_master_bruna_v12.csv` pode ser exportada pelo botão do Dashboard Master V12.