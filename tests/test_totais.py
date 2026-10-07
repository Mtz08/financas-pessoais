"""Resultado considera só o que foi pago; pendentes aparecem à parte."""

from datetime import date

from apps.dashboard.services import resumo_do_mes
from apps.lancamentos.models import Lancamento
from apps.lancamentos.services.dados import DadosTransferencia
from apps.lancamentos.services.lancamentos import alternar_status, criar_lancamento
from apps.lancamentos.services.transferencias import criar_transferencia
from apps.relatorios.services import totais
from core import dates

MARCO = date(2026, 3, 1)


def _lancar(despesa, salario, *, receita_paga=0, receita_pendente=0, despesa_paga=0, despesa_pendente=0):
    for tipo, categoria, valor, status in [
        ("RECEITA", salario, receita_paga, "PAGO"), ("RECEITA", salario, receita_pendente, "PENDENTE"),
        ("DESPESA", None, despesa_paga, "PAGO"), ("DESPESA", None, despesa_pendente, "PENDENTE"),
    ]:
        if valor:
            campos = {"tipo": tipo, "valor_centavos": valor, "status": status}
            if categoria:
                campos["categoria"] = categoria
            criar_lancamento(despesa(**campos))


def test_pendentes_nao_entram_no_resultado(despesa, salario):
    _lancar(despesa, salario, receita_paga=100_000, receita_pendente=50_000, despesa_paga=30_000,
            despesa_pendente=20_000)
    t = totais(Lancamento.objects.all())
    assert (t.receitas, t.despesas, t.resultado) == (100_000, 30_000, 70_000)
    assert (t.receitas_pendentes, t.despesas_pendentes) == (50_000, 20_000)


def test_ao_marcar_como_pago_entra_no_resultado(despesa, salario):
    _lancar(despesa, salario, receita_paga=100_000, despesa_pendente=20_000)
    assert totais(Lancamento.objects.all()).resultado == 100_000
    alternar_status(Lancamento.objects.get(status="PENDENTE"))
    t = totais(Lancamento.objects.all())
    assert (t.resultado, t.despesas_pendentes) == (80_000, 0)


def test_dashboard_usa_a_mesma_regra(despesa, salario):
    _lancar(despesa, salario, receita_paga=100_000, receita_pendente=50_000, despesa_pendente=20_000)
    resumo = resumo_do_mes(MARCO)
    assert (resumo.receitas, resumo.despesas, resumo.resultado) == (100_000, 0, 100_000)


def test_transferencia_nunca_conta(despesa, salario, corrente, carteira):
    criar_transferencia(DadosTransferencia(corrente, carteira, 9_999, date(2026, 3, 5)))
    t = totais(Lancamento.objects.all())
    assert (t.receitas, t.despesas, t.receitas_pendentes, t.despesas_pendentes) == (0, 0, 0, 0)


def test_telas_mostram_pendentes_a_parte(cliente_logado, despesa, salario):
    hoje = dates.hoje()
    criar_lancamento(despesa(valor_centavos=12_345, status="PENDENTE", data=hoje))
    for url in ["/", "/lancamentos/"]:
        html = cliente_logado.get(url).content.decode()
        assert "R$ 123,45 a pagar" in html, url
