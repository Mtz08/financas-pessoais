# Deploy: Render (app) + Neon (PostgreSQL)

> Os planos gratuitos mudam com frequência. Confira os limites atuais no site de cada
> provedor antes de publicar. A versão do Python vem do arquivo `.python-version` (3.13);
> sem ele, o Render usaria o padrão dele (3.14.x em 2026), não testado neste projeto.

## 1. Banco no Neon

1. Crie um projeto em neon.tech.
2. Copie a *connection string* no formato `postgres://usuario:senha@host/banco?sslmode=require`.

## 2. App no Render

1. Envie o repositório ao GitHub (o `.env` está no `.gitignore` e não sobe).
2. No Render: **New → Blueprint** e aponte para o repositório (usa o `render.yaml`).
3. Preencha as variáveis marcadas como `sync: false`:
   - `DATABASE_URL`: a URL do Neon.
   - `ALLOWED_HOSTS`: `seu-app.onrender.com`.
   - `CSRF_TRUSTED_ORIGINS`: `https://seu-app.onrender.com`.
4. Após o primeiro deploy, abra o **Shell** do serviço e crie seu usuário:
   `python manage.py createsuperuser`

O build roda `collectstatic` e `migrate` automaticamente a cada deploy.

## Observações

- **Hibernação:** no plano free, o app dorme quando fica ocioso; o primeiro acesso demora alguns segundos.
- **Recorrências:** são geradas quando você abre o dashboard ou a lista de lançamentos; não depende de cron.
- **Backup:** faça download periódico em *Backup → Baixar backup*. O Neon também guarda histórico, mas o arquivo é a sua cópia independente.
- **Docker:** o `Dockerfile` permite rodar em Fly.io, numa VPS ou localmente, com as mesmas variáveis de ambiente.
