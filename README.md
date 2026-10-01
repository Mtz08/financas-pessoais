# Finanças Pessoais

Sistema web de finanças pessoais para um único usuário: contas, cartões com fatura,
parcelamentos, recorrências, orçamento com alertas, dashboard, relatórios em CSV e backup.

**Stack:** Python 3.13 · Django 5.2 · PostgreSQL (produção) / SQLite (dev) · Pico.css · Chart.js.

## Rodar localmente (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env        # troque SECRET_KEY por um valor aleatório
python manage.py migrate
python manage.py createsuperuser   # seu único usuário
python manage.py seed              # opcional: dados fictícios para explorar
python manage.py runserver
```

Acesse http://localhost:8000. Para abrir pelo celular na mesma rede, rode
`python manage.py runserver 0.0.0.0:8000`, inclua o IP do PC em `ALLOWED_HOSTS`
e `CSRF_TRUSTED_ORIGINS` no `.env` e acesse `http://IP-DO-PC:8000`.

## Testes

```powershell
pytest
```

Cobrem: dinheiro e datas, saldo, transferência atômica, parcelamento (arredondamento,
faturas, escopos), fatura (fechamento, dia 31, pagamento), recorrência (geração
idempotente, escopos), orçamento (80%/100%), backup e segurança (login, bloqueio,
CSRF, XSS, CSP, duplo envio, CSV injection, open redirect). O CI roda em SQLite e PostgreSQL.

## Comandos úteis

| Comando | O que faz |
|---|---|
| `python manage.py seed --apagar` | Recria os dados fictícios (só com `DEBUG=True`) |
| `python manage.py gerar_recorrencias` | Gera os lançamentos fixos (também roda ao abrir o dashboard) |
| `python manage.py axes_reset` | Desbloqueia o login após 5 tentativas erradas |

## Documentação

- [Modelo de dados](docs/modelo-dados.md)
- [Regras de negócio](docs/regras.md)
- [Deploy no Render + Neon](docs/deploy.md)
