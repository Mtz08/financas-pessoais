"""Receitas e despesas avulsas (sem parcela, recorrência ou transferência)."""

from apps.cartoes.services import fatura_se_cartao
from apps.lancamentos.models import Lancamento
from core.exceptions import RegraDeNegocio

from .dados import DadosLancamento
from .validacao import validar_dados


def criar_lancamento(dados: DadosLancamento, fatura=None, **vinculos) -> Lancamento:
    validar_dados(dados)
    lancamento = Lancamento(**_campos(dados), **vinculos)
    lancamento.fatura = fatura or fatura_se_cartao(dados.conta, dados.data)
    lancamento.save()
    return lancamento


def atualizar_lancamento(lancamento: Lancamento, dados: DadosLancamento) -> Lancamento:
    if lancamento.eh_transferencia:
        raise RegraDeNegocio("Transferências são editadas pela tela de transferência.")
    validar_dados(dados, anterior=lancamento)
    mudou_conta_ou_data = lancamento.conta_id != dados.conta.pk or lancamento.data != dados.data
    for campo, valor in _campos(dados).items():
        setattr(lancamento, campo, valor)
    if mudou_conta_ou_data:
        lancamento.fatura = fatura_se_cartao(dados.conta, dados.data)
    lancamento.save()
    return lancamento


def alternar_status(lancamento: Lancamento) -> Lancamento:
    pago = lancamento.status == Lancamento.Status.PAGO
    lancamento.status = Lancamento.Status.PENDENTE if pago else Lancamento.Status.PAGO
    lancamento.save(update_fields=["status", "atualizado_em"])
    return lancamento


def _campos(dados: DadosLancamento) -> dict:
    return {
        "tipo": dados.tipo,
        "conta": dados.conta,
        "categoria": dados.categoria,
        "descricao": dados.descricao.strip(),
        "valor_centavos": dados.valor_centavos,
        "data": dados.data,
        "status": dados.status,
    }
