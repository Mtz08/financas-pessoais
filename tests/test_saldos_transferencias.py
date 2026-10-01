from datetime import date
from unittest import mock

import pytest
from django.db import IntegrityError

from apps.lancamentos.models import Lancamento
from apps.lancamentos.services.dados import DadosTransferencia
from apps.lancamentos.services.lancamentos import criar_lancamento
from apps.lancamentos.services.operacoes import excluir
from apps.lancamentos.services.saldos import saldo_conta
from apps.lancamentos.services.transferencias import atualizar_transferencia, criar_transferencia
from core.exceptions import RegraDeNegocio

ATE = date(2026, 12, 31)


def test_saldo_soma_receitas_e_subtrai_despesas_pagas(corrente, despesa, salario):
    criar_lancamento(despesa(tipo="RECEITA", categoria=salario, valor_centavos=500_000))
    criar_lancamento(despesa(valor_centavos=120_050))
    assert saldo_conta(corrente, ate=ATE) == 100_000 + 500_000 - 120_050


def test_pendente_so_entra_na_previsao(corrente, despesa):
    criar_lancamento(despesa(valor_centavos=30_000, status="PENDENTE"))
    assert saldo_conta(corrente, ate=ATE) == 100_000
    assert saldo_conta(corrente, ate=ATE, incluir_pendentes=True) == 70_000


def test_ignora_lancamentos_antes_do_saldo_inicial_e_depois_da_data(corrente, despesa):
    criar_lancamento(despesa(data=date(2025, 12, 31)))  # antes do saldo inicial
    criar_lancamento(despesa(data=date(2026, 6, 1)))
    assert saldo_conta(corrente, ate=date(2026, 5, 31)) == 100_000
    assert saldo_conta(corrente, ate=ATE) == 99_000


def test_compra_no_cartao_gera_divida_mesmo_pendente(cartao, despesa):
    criar_lancamento(despesa(conta=cartao, valor_centavos=25_000, status="PENDENTE"))
    assert saldo_conta(cartao, ate=ATE) == -25_000


def test_transferencia_debita_origem_credita_destino_e_preserva_total(corrente, carteira):
    total_antes = saldo_conta(corrente, ate=ATE) + saldo_conta(carteira, ate=ATE)
    saida, entrada = criar_transferencia(DadosTransferencia(corrente, carteira, 20_000, date(2026, 3, 1)))
    assert saida.transferencia_id == entrada.transferencia_id
    assert saldo_conta(corrente, ate=ATE) == 80_000
    assert saldo_conta(carteira, ate=ATE) == 25_000
    assert saldo_conta(corrente, ate=ATE) + saldo_conta(carteira, ate=ATE) == total_antes


def test_transferencia_e_atomica_se_o_credito_falhar_o_debito_e_desfeito(corrente, carteira):
    criar_original = Lancamento.objects.create
    chamadas = []

    def falha_no_segundo_insert(**campos):
        chamadas.append(campos["tipo"])
        if len(chamadas) == 2:
            raise IntegrityError("falha simulada ao gravar o crédito")
        return criar_original(**campos)

    with mock.patch.object(Lancamento.objects, "create", side_effect=falha_no_segundo_insert):
        with pytest.raises(IntegrityError):
            criar_transferencia(DadosTransferencia(corrente, carteira, 20_000, date(2026, 3, 1)))

    assert chamadas == ["TRANSF_SAIDA", "TRANSF_ENTRADA"]
    assert not Lancamento.objects.exists()  # a saída foi desfeita
    assert saldo_conta(corrente, ate=ATE) == 100_000


def test_transferencia_para_a_mesma_conta_e_recusada(corrente):
    with pytest.raises(RegraDeNegocio):
        criar_transferencia(DadosTransferencia(corrente, corrente, 1_000, date(2026, 3, 1)))


def test_transferencia_com_conta_arquivada_e_recusada(corrente, carteira):
    carteira.ativo = False
    carteira.save()
    with pytest.raises(RegraDeNegocio):
        criar_transferencia(DadosTransferencia(corrente, carteira, 1_000, date(2026, 3, 1)))


def test_excluir_uma_ponta_exclui_a_transferencia_inteira(corrente, carteira):
    saida, _ = criar_transferencia(DadosTransferencia(corrente, carteira, 1_000, date(2026, 3, 1)))
    excluir(saida)
    assert not Lancamento.objects.exists()


def test_editar_transferencia_mantem_um_unico_par(corrente, carteira):
    saida, _ = criar_transferencia(DadosTransferencia(corrente, carteira, 1_000, date(2026, 3, 1)))
    atualizar_transferencia(saida, DadosTransferencia(corrente, carteira, 7_500, date(2026, 3, 2)))
    assert Lancamento.objects.count() == 2
    assert set(Lancamento.objects.values_list("valor_centavos", flat=True)) == {7_500}
    assert saldo_conta(carteira, ate=ATE) == 12_500


def test_banco_recusa_meia_transferencia(corrente):
    """Mesmo sem passar pelo serviço, o banco exige transferencia_id e proíbe categoria."""
    with pytest.raises(IntegrityError):
        Lancamento.objects.create(tipo="TRANSF_SAIDA", conta=corrente, descricao="x", valor_centavos=1,
                                  data=date(2026, 3, 1))
