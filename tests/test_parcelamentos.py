from datetime import date

import pytest

from apps.lancamentos.models import Lancamento, Parcelamento
from apps.lancamentos.services.dados import DadosLancamento, DadosParcelamento, Escopo
from apps.lancamentos.services.operacoes import editar, excluir
from apps.lancamentos.services.parcelamentos import criar_parcelamento
from core.exceptions import RegraDeNegocio


@pytest.fixture
def parcelar(corrente, mercado):
    def fabricar(**campos) -> Parcelamento:
        padrao = {"conta": corrente, "categoria": mercado, "descricao": "Geladeira fictícia",
                  "valor_total_centavos": 10_000, "quantidade_parcelas": 3, "data_compra": date(2026, 1, 31)}
        return criar_parcelamento(DadosParcelamento(**{**padrao, **campos}))
    return fabricar


def _parcelas(parcelamento):
    return list(parcelamento.parcelas.order_by("numero_parcela"))


def test_gera_n_parcelas_com_centavos_na_ultima(parcelar):
    parcelas = _parcelas(parcelar())
    assert [p.valor_centavos for p in parcelas] == [3333, 3333, 3334]
    assert [p.numero_parcela for p in parcelas] == [1, 2, 3]
    assert parcelas[1].descricao_completa == "Geladeira fictícia (2/3)"


def test_parcelas_mensais_respeitam_meses_curtos(parcelar):
    datas = [p.data for p in _parcelas(parcelar())]
    assert datas == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


def test_no_cartao_cada_parcela_vai_para_a_fatura_seguinte(parcelar, cartao):
    # Compra em 26/03, depois do fechamento (25): 1ª parcela na fatura que vence em 05/05.
    parcelas = _parcelas(parcelar(conta=cartao, data_compra=date(2026, 3, 26), quantidade_parcelas=4))
    assert [p.fatura.competencia for p in parcelas] == [
        date(2026, 5, 1), date(2026, 6, 1), date(2026, 7, 1), date(2026, 8, 1)]


@pytest.mark.parametrize(("quantidade", "valor"), [(1, 10_000), (73, 100_000), (5, 4)])
def test_quantidade_ou_valor_invalido_e_recusado(parcelar, quantidade, valor):
    with pytest.raises(RegraDeNegocio):
        parcelar(quantidade_parcelas=quantidade, valor_total_centavos=valor)
    assert not Parcelamento.objects.exists()


def _dados(parcela, **campos) -> DadosLancamento:
    return DadosLancamento.de_lancamento(parcela).com(**campos)


def test_editar_somente_esta(parcelar):
    p1, p2, p3 = _parcelas(parcelar())
    editar(p2, _dados(p2, valor_centavos=5_000), Escopo.ESTA)
    assert [p.valor_centavos for p in _parcelas(p1.parcelamento)] == [3333, 5000, 3334]


def test_editar_esta_e_as_proximas_mantem_datas(parcelar):
    p1, p2, p3 = _parcelas(parcelar())
    editar(p2, _dados(p2, descricao="Geladeira nova", valor_centavos=4_000), Escopo.ESTA_E_PROXIMAS)
    atualizadas = _parcelas(p1.parcelamento)
    assert [p.descricao for p in atualizadas] == ["Geladeira fictícia", "Geladeira nova", "Geladeira nova"]
    assert [p.valor_centavos for p in atualizadas] == [3333, 4000, 4000]
    assert [p.data for p in atualizadas] == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


def test_editar_todas_atualiza_o_cabecalho(parcelar):
    parcelamento = parcelar()
    p1 = _parcelas(parcelamento)[0]
    editar(p1, _dados(p1, descricao="Refrigerador"), Escopo.TODAS)
    parcelamento.refresh_from_db()
    assert parcelamento.descricao == "Refrigerador"
    assert {p.descricao for p in _parcelas(parcelamento)} == {"Refrigerador"}


def test_trocar_conta_de_varias_parcelas_e_recusado(parcelar, carteira):
    p1 = _parcelas(parcelar())[0]
    with pytest.raises(RegraDeNegocio):
        editar(p1, _dados(p1, conta=carteira), Escopo.TODAS)


def test_excluir_somente_esta(parcelar):
    parcelamento = parcelar()
    excluir(_parcelas(parcelamento)[0], Escopo.ESTA)
    assert [p.numero_parcela for p in _parcelas(parcelamento)] == [2, 3]


def test_excluir_esta_e_as_proximas(parcelar):
    parcelamento = parcelar()
    excluir(_parcelas(parcelamento)[1], Escopo.ESTA_E_PROXIMAS)
    assert [p.numero_parcela for p in _parcelas(parcelamento)] == [1]


def test_excluir_todas_remove_o_cabecalho(parcelar):
    parcelamento = parcelar()
    excluir(_parcelas(parcelamento)[1], Escopo.TODAS)
    assert not Parcelamento.objects.exists()
    assert not Lancamento.objects.exists()
