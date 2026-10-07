"""Pagamento de fatura = transferência da conta corrente/carteira para o cartão."""

from datetime import date

from django.db import transaction

from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento
from apps.lancamentos.services.dados import DadosTransferencia
from apps.lancamentos.services.transferencias import criar_transferencia
from core.exceptions import RegraDeNegocio

from .models import Fatura
from .services import resumir_fatura


@transaction.atomic
def pagar_fatura(fatura: Fatura, conta_origem: Conta, valor_centavos: int, data: date) -> None:
    if conta_origem.dono_id != fatura.conta.dono_id:
        raise RegraDeNegocio("A conta de pagamento pertence a outro usuário.")
    if conta_origem.eh_cartao:
        raise RegraDeNegocio("A fatura deve ser paga a partir de conta corrente ou dinheiro.")
    criar_transferencia(
        DadosTransferencia(
            origem=conta_origem,
            destino=fatura.conta,
            valor_centavos=valor_centavos,
            data=data,
            descricao=f"Pagamento fatura {fatura.conta} {fatura.competencia:%m/%Y}",
        ),
        fatura_destino=fatura,
    )
    if resumir_fatura(fatura).restante_centavos == 0:
        fatura.lancamentos.filter(
            tipo=Lancamento.Tipo.DESPESA, status=Lancamento.Status.PENDENTE
        ).update(status=Lancamento.Status.PAGO)
