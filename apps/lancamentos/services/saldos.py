from datetime import date

from django.db.models import Q, Sum

from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento
from core import dates

ENTRADAS = Q(tipo__in=Lancamento.TIPOS_ENTRADA)


def saldo_conta(conta: Conta, ate: date | None = None, incluir_pendentes: bool = False) -> int:
    """Saldo em centavos = saldo inicial + entradas - saídas até a data.

    Conta corrente/carteira: só conta o que está PAGO (pendente é previsão).
    Cartão: toda compra já compromete o limite, paga ou não; saldo
    negativo = valor devido.
    """
    ate = ate or dates.hoje()
    lancamentos = conta.lancamentos.filter(data__gte=conta.data_saldo_inicial, data__lte=ate)
    if not incluir_pendentes:
        lancamentos = lancamentos.filter(_filtro_efetivado(conta))
    somas = lancamentos.aggregate(
        entradas=Sum("valor_centavos", filter=ENTRADAS),
        saidas=Sum("valor_centavos", filter=~ENTRADAS),
    )
    return conta.saldo_inicial_centavos + (somas["entradas"] or 0) - (somas["saidas"] or 0)


def _filtro_efetivado(conta: Conta) -> Q:
    pago = Q(status=Lancamento.Status.PAGO)
    if conta.eh_cartao:
        return pago | Q(tipo__in=[Lancamento.Tipo.RECEITA, Lancamento.Tipo.DESPESA])
    return pago


def saldos_das_contas(usuario, ate: date | None = None) -> list[tuple[Conta, int]]:
    contas = Conta.objects.do_usuario(usuario).filter(ativo=True)
    return [(conta, saldo_conta(conta, ate)) for conta in contas]


def saldo_disponivel(usuario, ate: date | None = None) -> int:
    """Soma de conta corrente + dinheiro (cartão fica de fora: é dívida)."""
    return sum(saldo for conta, saldo in saldos_das_contas(usuario, ate) if not conta.eh_cartao)
