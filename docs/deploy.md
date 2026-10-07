# Deploy: Render (site) + Neon (PostgreSQL)

Limites conferidos na documentação dos provedores em 07/10/2026. Os planos gratuitos
mudam com frequência; confira antes de publicar.

| | Render (free) | Neon (free) |
|---|---|---|
| Custo | Gratuito | Gratuito, sem prazo de expiração |
| Limite | 750 h/mês por workspace | 1 GB por projeto, 100 CU-hora/mês |
| Ociosidade | Dorme após 15 min sem acesso; o 1º acesso leva cerca de 1 min | Suspende após 5 min; volta em instantes |
| Shell/SSH | **Não disponível** | — |

A versão do Python vem do arquivo `.python-version` (3.13).

## 1. Banco no Neon

1. Crie uma conta em **neon.tech** e um projeto na região **AWS US East 2 (Ohio)**, a mesma do
   `render.yaml` (o Render não tem região no Brasil; site e banco perto um do outro é o que importa).
   Deixe ligado só o "Banco de dados Postgres".
2. Em **Connect**, copie a *connection string*. Ela tem o formato
   `postgresql://usuario:senha@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require`.
3. Guarde essa URL: ela é a senha do seu banco. Não a coloque no GitHub.

## 2. Site no Render

1. Crie uma conta em **render.com** entrando com o GitHub.
2. **New → Blueprint** e escolha o repositório `Financas_Web` (o Render lê o `render.yaml`).
3. Quando pedir `DATABASE_URL`, cole a URL do Neon.
4. Confirme. O build instala as dependências, roda `collectstatic` e aplica as migrações no Neon.

`ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` não precisam ser preenchidos: o sistema usa o
domínio que o Render informa em `RENDER_EXTERNAL_HOSTNAME`.

## 3. Criar seu usuário (a partir do seu PC)

O plano free não tem Shell, então o usuário é criado no seu computador, apontando para o
banco do Neon. No PowerShell, na pasta do projeto:

```powershell
$env:DATABASE_URL = "COLE_AQUI_A_URL_DO_NEON"
.\.venv\Scripts\python.exe manage.py createsuperuser
Remove-Item Env:DATABASE_URL
```

Use uma senha forte (12+ caracteres): o site fica exposto na internet. Se o comando avisar
que a senha é fraca e perguntar se quer ignorar, responda **N** e escolha outra.

O `Remove-Item` no final volta o PowerShell para o banco local.

## 4. Usar pelo celular

Abra `https://financas-xxxx.onrender.com` (o endereço aparece no painel do Render).
No Chrome/Android, use **Adicionar à tela inicial**; no Safari/iPhone, **Compartilhar →
Adicionar à Tela de Início**.

## Manutenção

- **Atualizações:** cada `git push` na `master` gera um novo deploy automaticamente.
- **Backup:** baixe periodicamente em *Backup → Baixar backup*.
- **Login bloqueado (5 senhas erradas):** espere 1 hora, ou rode `axes_reset` do seu PC com
  `$env:DATABASE_URL` apontando para o Neon, como no passo 3.
- **Docker:** o `Dockerfile` permite rodar em Fly.io, numa VPS ou localmente, com as mesmas
  variáveis de ambiente.
