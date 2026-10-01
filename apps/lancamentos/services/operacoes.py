"""Ponto único para editar/excluir qualquer lançamento: decide qual
serviço aplicar conforme o lançamento seja parcela, recorrência,
transferência ou avulso."""

from apps.lancamentos.models import Lancamento

from . import parcelamentos, recorrencias, transferencias
from .dados import DadosLancamento, Escopo
from .lancamentos import atualizar_lancamento


def aceita_escopo(lancamento: Lancamento) -> bool:
    return bool(lancamento.parcelamento_id or lancamento.recorrencia_id)


def editar(lancamento: Lancamento, dados: DadosLancamento, escopo: Escopo = Escopo.ESTA) -> None:
    if lancamento.parcelamento_id:
        parcelamentos.editar_parcela(lancamento, dados, escopo)
    elif lancamento.recorrencia_id:
        recorrencias.editar_ocorrencia(lancamento, dados, escopo)
    else:
        atualizar_lancamento(lancamento, dados)


def excluir(lancamento: Lancamento, escopo: Escopo = Escopo.ESTA) -> None:
    if lancamento.eh_transferencia:
        transferencias.excluir_transferencia(lancamento)
    elif lancamento.parcelamento_id:
        parcelamentos.excluir_parcela(lancamento, escopo)
    elif lancamento.recorrencia_id:
        recorrencias.excluir_ocorrencia(lancamento, escopo)
    else:
        lancamento.delete()
