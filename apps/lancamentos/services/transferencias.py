"""Transferência = dois lançamentos (saída + entrada) na MESMA transação."""

import uuid

from django.db import transaction

from apps.cartoes.models import Fatura
from apps.cartoes.services import fatura_se_cartao
from apps.lancamentos.models import Lancamento
from core.exceptions import RegraDeNegocio

from .dados import DadosTransferencia
from .validacao import validar_conta_ativa, validar_mesmo_dono, validar_valor


def _validar(dados: DadosTransferencia) -> None:
    if dados.origem.pk == dados.destino.pk:
        raise RegraDeNegocio("Origem e destino devem ser contas diferentes.")
    validar_mesmo_dono(dados.origem, dados.destino)
    validar_conta_ativa(dados.origem)
    validar_conta_ativa(dados.destino)
    validar_valor(dados.valor_centavos)


@transaction.atomic
def criar_transferencia(
    dados: DadosTransferencia, fatura_destino: Fatura | None = None
) -> tuple[Lancamento, Lancamento]:
    """Debita a origem e credita o destino. Se qualquer INSERT falhar,
    o `atomic` desfaz tudo: nunca existe meia transferência."""
    _validar(dados)
    comum = {
        "valor_centavos": dados.valor_centavos,
        "data": dados.data,
        "status": dados.status,
        "descricao": dados.descricao.strip() or "Transferência",
        "transferencia_id": uuid.uuid4(),
    }
    saida = Lancamento.objects.create(
        tipo=Lancamento.Tipo.TRANSF_SAIDA,
        conta=dados.origem,
        fatura=fatura_se_cartao(dados.origem, dados.data),
        **comum,
    )
    entrada = Lancamento.objects.create(
        tipo=Lancamento.Tipo.TRANSF_ENTRADA,
        conta=dados.destino,
        fatura=fatura_destino or fatura_se_cartao(dados.destino, dados.data),
        **comum,
    )
    return saida, entrada


def par_da_transferencia(lancamento: Lancamento) -> tuple[Lancamento, Lancamento]:
    par = {item.tipo: item for item in Lancamento.objects.filter(transferencia_id=lancamento.transferencia_id)}
    return par[Lancamento.Tipo.TRANSF_SAIDA], par[Lancamento.Tipo.TRANSF_ENTRADA]


@transaction.atomic
def atualizar_transferencia(lancamento: Lancamento, dados: DadosTransferencia) -> tuple[Lancamento, Lancamento]:
    """Recria o par com os novos dados. Se o destino não mudou, o pagamento
    continua ligado à mesma fatura."""
    _, entrada = par_da_transferencia(lancamento)
    fatura_destino = entrada.fatura if entrada.conta_id == dados.destino.pk else None
    excluir_transferencia(lancamento)
    return criar_transferencia(dados, fatura_destino=fatura_destino)


@transaction.atomic
def excluir_transferencia(lancamento: Lancamento) -> None:
    Lancamento.objects.filter(transferencia_id=lancamento.transferencia_id).delete()
