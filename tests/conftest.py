"""Fixtures compartilhadas. Todos os dados são fictícios."""

from datetime import date

import pytest
from django.contrib.auth.models import User

from apps.categorias.models import Categoria
from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento
from apps.lancamentos.services.dados import DadosLancamento

SENHA_TESTE = "SenhaFicticia#2026"


@pytest.fixture
def corrente(usuario):
    return Conta.objects.create(
        dono=usuario, nome="Banco Teste", tipo=Conta.Tipo.CORRENTE, saldo_inicial_centavos=100_000,
        data_saldo_inicial=date(2026, 1, 1),
    )


@pytest.fixture
def carteira(usuario):
    return Conta.objects.create(
        dono=usuario, nome="Carteira Teste", tipo=Conta.Tipo.CARTEIRA, saldo_inicial_centavos=5_000,
        data_saldo_inicial=date(2026, 1, 1),
    )


@pytest.fixture
def cartao(usuario):
    """Fecha dia 25, vence dia 5 do mês seguinte."""
    return Conta.objects.create(
        dono=usuario, nome="Cartão Teste", tipo=Conta.Tipo.CARTAO, data_saldo_inicial=date(2026, 1, 1),
        dia_fechamento=25, dia_vencimento=5,
    )


@pytest.fixture
def mercado(usuario):
    pai = Categoria.objects.create(dono=usuario, nome="Alimentação", tipo=Categoria.Tipo.DESPESA)
    return Categoria.objects.create(dono=usuario, nome="Mercado", tipo=Categoria.Tipo.DESPESA, pai=pai)


@pytest.fixture
def salario(usuario):
    return Categoria.objects.create(dono=usuario, nome="Salário", tipo=Categoria.Tipo.RECEITA)


@pytest.fixture
def despesa(corrente, mercado):
    """Fábrica de DadosLancamento de despesa com valores padrão sobrescrevíveis."""

    def fabricar(**campos) -> DadosLancamento:
        padrao = {
            "tipo": Lancamento.Tipo.DESPESA, "conta": corrente, "categoria": mercado,
            "descricao": "Compra fictícia", "valor_centavos": 1_000, "data": date(2026, 3, 10),
            "status": Lancamento.Status.PAGO,
        }
        return DadosLancamento(**{**padrao, **campos})

    return fabricar


@pytest.fixture
def usuario(db):
    return User.objects.create_user("usuario_teste", password=SENHA_TESTE)


@pytest.fixture
def cliente_logado(client, usuario):
    client.post("/entrar/", {"username": usuario.username, "password": SENHA_TESTE})
    return client


@pytest.fixture(autouse=True)
def _configuracao_de_teste(settings):
    settings.ALLOWED_HOSTS = ["testserver"]
    # Sem collectstatic nos testes: storage simples em vez do manifesto com hash.
    settings.STORAGES = {**settings.STORAGES, "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
