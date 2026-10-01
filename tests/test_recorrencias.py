from datetime import date

import pytest

from apps.lancamentos.models import Lancamento, Recorrencia
from apps.lancamentos.services import recorrencias
from apps.lancamentos.services.dados import DadosLancamento, Escopo
from apps.lancamentos.services.operacoes import editar, excluir
from apps.lancamentos.services.recorrencias import DadosRecorrencia, criar_recorrencia, gerar_todas
from core import dates

HOJE = date(2026, 3, 15)  # horizonte = HOJE + 2 meses = 31/05/2026


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    monkeypatch.setattr(dates, "hoje", lambda: HOJE)


@pytest.fixture
def aluguel(corrente, mercado):
    return criar_recorrencia(DadosRecorrencia("DESPESA", corrente, mercado, "Aluguel fictício", 150_000, 31,
                                              date(2026, 1, 1)))


def _ocorrencias(recorrencia=None):
    consulta = Lancamento.objects.filter(recorrencia__isnull=False).order_by("data")
    return list(consulta.filter(recorrencia=recorrencia) if recorrencia else consulta)


def test_gera_uma_ocorrencia_por_mes_ate_o_horizonte(aluguel):
    assert [l.data for l in _ocorrencias()] == [
        date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30), date(2026, 5, 31)]
    assert all(l.status == "PENDENTE" for l in _ocorrencias())


def test_gerar_de_novo_nao_duplica(aluguel):
    assert gerar_todas() == 0
    assert gerar_todas(ate=date(2026, 5, 31)) == 0
    assert len(_ocorrencias()) == 5


def test_gera_os_meses_seguintes_quando_o_tempo_passa(aluguel, monkeypatch):
    monkeypatch.setattr(dates, "hoje", lambda: date(2026, 5, 2))
    assert gerar_todas() == 2  # junho e julho
    assert _ocorrencias()[-1].data == date(2026, 7, 31)


def test_respeita_data_de_fim(corrente, mercado):
    criar_recorrencia(DadosRecorrencia("DESPESA", corrente, mercado, "Curso", 9_900, 10, date(2026, 1, 1),
                                       data_fim=date(2026, 3, 9)))
    assert [l.data for l in _ocorrencias()] == [date(2026, 1, 10), date(2026, 2, 10)]


def test_excluir_somente_esta_nao_volta_na_proxima_geracao(aluguel, monkeypatch):
    excluir(_ocorrencias()[1], Escopo.ESTA)
    monkeypatch.setattr(dates, "hoje", lambda: date(2026, 6, 1))
    gerar_todas()
    assert date(2026, 2, 28) not in [l.data for l in _ocorrencias()]


def _dados(lancamento, **campos):
    return DadosLancamento.de_lancamento(lancamento).com(**campos)


def test_editar_somente_esta(aluguel):
    marco = _ocorrencias()[2]
    editar(marco, _dados(marco, valor_centavos=160_000), Escopo.ESTA)
    assert [l.valor_centavos for l in _ocorrencias()] == [150_000, 150_000, 160_000, 150_000, 150_000]


def test_editar_esta_e_as_proximas_divide_a_recorrencia(aluguel, monkeypatch):
    Lancamento.objects.filter(data__lt=date(2026, 3, 1)).update(status="PAGO")
    marco = _ocorrencias()[2]
    editar(marco, _dados(marco, valor_centavos=165_000, data=date(2026, 3, 5)), Escopo.ESTA_E_PROXIMAS)

    aluguel.refresh_from_db()
    nova = Recorrencia.objects.exclude(pk=aluguel.pk).get()
    assert aluguel.data_fim == date(2026, 2, 28)
    assert (nova.data_inicio, nova.valor_centavos, nova.dia) == (date(2026, 3, 1), 165_000, 5)
    assert [l.valor_centavos for l in _ocorrencias(aluguel)] == [150_000, 150_000]
    assert [(l.data, l.valor_centavos) for l in _ocorrencias(nova)] == [
        (date(2026, 3, 5), 165_000), (date(2026, 4, 5), 165_000), (date(2026, 5, 5), 165_000)]

    monkeypatch.setattr(dates, "hoje", lambda: date(2026, 4, 10))
    gerar_todas()  # junho sai pelo molde novo; o antigo não gera mais nada
    assert _ocorrencias(aluguel)[-1].data == date(2026, 2, 28)
    assert _ocorrencias(nova)[-1].valor_centavos == 165_000


def test_editar_todas_preserva_as_ja_pagas(aluguel):
    Lancamento.objects.filter(data__lt=date(2026, 3, 1)).update(status="PAGO")
    abril = _ocorrencias()[3]
    editar(abril, _dados(abril, valor_centavos=170_000), Escopo.TODAS)
    assert [l.valor_centavos for l in _ocorrencias()] == [150_000, 150_000, 170_000, 170_000, 170_000]
    aluguel.refresh_from_db()
    assert aluguel.valor_centavos == 170_000


def test_excluir_esta_e_as_proximas_encerra_a_recorrencia(aluguel, monkeypatch):
    excluir(_ocorrencias()[2], Escopo.ESTA_E_PROXIMAS)
    aluguel.refresh_from_db()
    assert aluguel.data_fim == date(2026, 2, 28)
    assert [l.data for l in _ocorrencias()] == [date(2026, 1, 31), date(2026, 2, 28)]
    monkeypatch.setattr(dates, "hoje", lambda: date(2026, 8, 1))
    gerar_todas()
    assert len(_ocorrencias()) == 2


def test_excluir_todas_mantem_o_historico_pago(aluguel):
    Lancamento.objects.filter(data__lt=date(2026, 2, 1)).update(status="PAGO")
    excluir(_ocorrencias()[3], Escopo.TODAS)
    assert not Recorrencia.objects.exists()
    restantes = list(Lancamento.objects.all())
    assert [(l.data, l.status, l.recorrencia_id) for l in restantes] == [(date(2026, 1, 31), "PAGO", None)]


def test_recorrencia_de_conta_arquivada_nao_gera(aluguel, corrente, monkeypatch):
    corrente.ativo = False
    corrente.save()
    monkeypatch.setattr(dates, "hoje", lambda: date(2026, 9, 1))
    assert recorrencias.gerar_todas() == 0
