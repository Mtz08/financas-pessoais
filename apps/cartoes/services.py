"""Regras de fatura de cartão de crédito.

Convenção: `competencia` = dia 1º do mês de VENCIMENTO da fatura.
Compra feita NO dia do fechamento ou depois cai na fatura seguinte.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Q, Sum

from apps.contas.models import Conta
from core import dates

from .models import Fatura


def datas_da_fatura(conta: Conta, competencia: date) -> tuple[date, date]:
    """Retorna (fechamento, vencimento) da fatura de `competencia`."""
    vencimento = dates.data_no_mes(competencia.year, competencia.month, conta.dia_vencimento)
    # Fecha no mesmo mês do vencimento se o dia de fechamento vem antes;
    # senão (ex.: fecha 28, vence 5), fecha no mês anterior.
    mes_fechamento = competencia if conta.dia_fechamento < conta.dia_vencimento else dates.somar_meses(competencia, -1)
    fechamento = dates.data_no_mes(mes_fechamento.year, mes_fechamento.month, conta.dia_fechamento)
    if fechamento >= vencimento:  # ex.: fecha 30 e vence 31 em fevereiro
        fechamento = vencimento - timedelta(days=1)
    return fechamento, vencimento


def competencia_da_compra(conta: Conta, data_compra: date) -> date:
    """Primeira fatura cujo fechamento é posterior à data da compra."""
    competencia = dates.primeiro_dia(data_compra)
    while data_compra >= datas_da_fatura(conta, competencia)[0]:
        competencia = dates.somar_meses(competencia, 1)
    return competencia


def obter_fatura(conta: Conta, competencia: date) -> Fatura:
    competencia = dates.primeiro_dia(competencia)
    fechamento, vencimento = datas_da_fatura(conta, competencia)
    fatura, _ = Fatura.objects.get_or_create(
        conta=conta,
        competencia=competencia,
        defaults={"data_fechamento": fechamento, "data_vencimento": vencimento},
    )
    return fatura


def fatura_da_compra(conta: Conta, data_compra: date) -> Fatura:
    return obter_fatura(conta, competencia_da_compra(conta, data_compra))


def fatura_se_cartao(conta: Conta, data_compra: date) -> Fatura | None:
    return fatura_da_compra(conta, data_compra) if conta.eh_cartao else None


@dataclass(frozen=True)
class ResumoFatura:
    fatura: Fatura
    total_centavos: int  # compras - estornos
    pago_centavos: int
    status: str  # ABERTA | FECHADA | VENCIDA | PAGA

    @property
    def restante_centavos(self) -> int:
        return max(self.total_centavos - self.pago_centavos, 0)


def resumir_fatura(fatura: Fatura, hoje: date | None = None) -> ResumoFatura:
    hoje = hoje or dates.hoje()
    somas = fatura.lancamentos.aggregate(
        saidas=Sum("valor_centavos", filter=Q(tipo__in=["DESPESA", "TRANSF_SAIDA"])),
        estornos=Sum("valor_centavos", filter=Q(tipo="RECEITA")),
        pagamentos=Sum("valor_centavos", filter=Q(tipo="TRANSF_ENTRADA")),
    )
    total = (somas["saidas"] or 0) - (somas["estornos"] or 0)
    pago = somas["pagamentos"] or 0
    return ResumoFatura(fatura, total, pago, _status_fatura(fatura, total, pago, hoje))


def _status_fatura(fatura: Fatura, total: int, pago: int, hoje: date) -> str:
    if hoje >= fatura.data_fechamento and pago >= total:
        return "PAGA"
    if hoje > fatura.data_vencimento:
        return "VENCIDA"
    if hoje >= fatura.data_fechamento:
        return "FECHADA"
    return "ABERTA"
