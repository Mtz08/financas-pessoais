from datetime import date

import pytest

from apps.cartoes.pagamentos import pagar_fatura
from apps.cartoes.services import competencia_da_compra, datas_da_fatura, fatura_da_compra, resumir_fatura
from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento
from apps.lancamentos.services.lancamentos import criar_lancamento
from core.exceptions import RegraDeNegocio


def _cartao(dia_fechamento, dia_vencimento):
    from django.contrib.auth.models import User
    dono, _ = User.objects.get_or_create(username="usuario_teste")
    return Conta.objects.create(dono=dono, nome=f"Cartão {dia_fechamento}/{dia_vencimento}", tipo="CARTAO",
                                data_saldo_inicial=date(2026, 1, 1),
                                dia_fechamento=dia_fechamento, dia_vencimento=dia_vencimento)


@pytest.mark.parametrize(
    ("compra", "competencia"),
    [
        (date(2026, 3, 24), date(2026, 4, 1)),   # antes do fechamento (25/03): vence 05/04
        (date(2026, 3, 25), date(2026, 5, 1)),   # NO dia do fechamento: fatura seguinte
        (date(2026, 3, 26), date(2026, 5, 1)),   # depois do fechamento: fatura seguinte
        (date(2026, 12, 26), date(2027, 2, 1)),  # virada de ano
    ],
)
def test_compra_cai_na_fatura_certa(cartao, compra, competencia):
    assert competencia_da_compra(cartao, compra) == competencia


def test_vencimento_dia_31_em_fevereiro_vira_dia_28(db):
    cartao = _cartao(dia_fechamento=20, dia_vencimento=31)
    assert datas_da_fatura(cartao, date(2026, 2, 1)) == (date(2026, 2, 20), date(2026, 2, 28))
    assert datas_da_fatura(cartao, date(2028, 2, 1)) == (date(2028, 2, 20), date(2028, 2, 29))


def test_fechamento_nunca_coincide_com_vencimento_em_mes_curto(db):
    cartao = _cartao(dia_fechamento=30, dia_vencimento=31)
    fechamento, vencimento = datas_da_fatura(cartao, date(2026, 2, 1))
    assert vencimento == date(2026, 2, 28)
    assert fechamento == date(2026, 2, 27)


def test_fatura_e_reaproveitada_e_guarda_as_datas(cartao):
    primeira = fatura_da_compra(cartao, date(2026, 3, 1))
    segunda = fatura_da_compra(cartao, date(2026, 3, 20))
    assert primeira.pk == segunda.pk
    cartao.dia_fechamento = 10  # mudar o cartão não altera a fatura já criada
    cartao.save()
    primeira.refresh_from_db()
    assert primeira.data_fechamento == date(2026, 3, 25)


def test_compra_no_cartao_e_vinculada_a_fatura(cartao, despesa):
    lancamento = criar_lancamento(despesa(conta=cartao, data=date(2026, 3, 26)))
    assert lancamento.fatura.competencia == date(2026, 5, 1)


def test_resumo_considera_estorno_e_pagamento(cartao, corrente, despesa, salario):
    criar_lancamento(despesa(conta=cartao, valor_centavos=30_000, data=date(2026, 3, 1)))
    criar_lancamento(despesa(conta=cartao, valor_centavos=20_000, data=date(2026, 3, 2)))
    estorno = despesa(conta=cartao, valor_centavos=5_000, data=date(2026, 3, 3), tipo="RECEITA", categoria=salario)
    criar_lancamento(estorno)
    fatura = fatura_da_compra(cartao, date(2026, 3, 1))
    assert resumir_fatura(fatura, hoje=date(2026, 3, 10)).total_centavos == 45_000
    assert resumir_fatura(fatura, hoje=date(2026, 3, 10)).status == "ABERTA"
    assert resumir_fatura(fatura, hoje=date(2026, 3, 30)).status == "FECHADA"
    assert resumir_fatura(fatura, hoje=date(2026, 4, 6)).status == "VENCIDA"

    pagar_fatura(fatura, corrente, 45_000, date(2026, 4, 5))
    resumo = resumir_fatura(fatura, hoje=date(2026, 4, 6))
    assert (resumo.pago_centavos, resumo.restante_centavos, resumo.status) == (45_000, 0, "PAGA")


def test_pagamento_total_marca_compras_como_pagas(cartao, corrente, despesa):
    criar_lancamento(despesa(conta=cartao, valor_centavos=10_000, status="PENDENTE"))
    fatura = fatura_da_compra(cartao, date(2026, 3, 10))

    pagar_fatura(fatura, corrente, 4_000, date(2026, 4, 1))
    assert fatura.lancamentos.filter(tipo="DESPESA", status="PENDENTE").count() == 1  # parcial: continua pendente

    pagar_fatura(fatura, corrente, 6_000, date(2026, 4, 2))
    assert not fatura.lancamentos.filter(tipo="DESPESA", status="PENDENTE").exists()


def test_fatura_nao_pode_ser_paga_com_outro_cartao(cartao, despesa):
    outro = _cartao(10, 20)
    criar_lancamento(despesa(conta=cartao))
    with pytest.raises(RegraDeNegocio):
        pagar_fatura(fatura_da_compra(cartao, date(2026, 3, 10)), outro, 1_000, date(2026, 4, 1))
    assert not Lancamento.objects.filter(tipo="TRANSF_SAIDA").exists()
