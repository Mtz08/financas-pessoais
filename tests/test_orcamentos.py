from datetime import date

import pytest

from apps.lancamentos.services.lancamentos import criar_lancamento
from apps.orcamentos.models import Orcamento
from apps.orcamentos.services import alertas_do_mes, situacao_do_mes

MARCO = date(2026, 3, 1)


@pytest.fixture
def limite_alimentacao(mercado):
    return Orcamento.objects.create(categoria=mercado.pai, vigente_desde=date(2026, 1, 1), limite_centavos=100_000)


@pytest.mark.parametrize(
    ("gasto", "nivel"),
    [(79_999, "ok"), (80_000, "alerta"), (99_999, "alerta"), (100_000, "estourado"), (150_000, "estourado")],
)
def test_niveis_de_alerta_em_80_e_100_por_cento(limite_alimentacao, despesa, usuario, gasto, nivel):
    criar_lancamento(despesa(valor_centavos=gasto))  # categoria Mercado (filha de Alimentação)
    [situacao] = situacao_do_mes(usuario, MARCO)
    assert situacao.gasto_centavos == gasto
    assert situacao.nivel == nivel


def test_ignora_outros_meses_e_receitas(limite_alimentacao, despesa, salario, usuario):
    criar_lancamento(despesa(valor_centavos=90_000, data=date(2026, 2, 28)))
    criar_lancamento(despesa(tipo="RECEITA", categoria=salario, valor_centavos=90_000))
    assert situacao_do_mes(usuario, MARCO)[0].gasto_centavos == 0
    assert alertas_do_mes(usuario, MARCO) == []


def test_vale_o_limite_mais_recente_vigente(limite_alimentacao, mercado, usuario):
    Orcamento.objects.create(categoria=mercado.pai, vigente_desde=date(2026, 3, 1), limite_centavos=50_000)
    assert situacao_do_mes(usuario, date(2026, 2, 1))[0].limite_centavos == 100_000
    assert situacao_do_mes(usuario, MARCO)[0].limite_centavos == 50_000
    assert situacao_do_mes(usuario, date(2026, 9, 1))[0].limite_centavos == 50_000
