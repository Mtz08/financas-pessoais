"""Consultas agregadas do dashboard. Transferências e pagamentos de fatura
não contam como receita/despesa (só movem dinheiro entre contas).
Compras no cartão contam na data da compra (regime de competência)."""

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce, TruncMonth

from apps.cartoes.models import Fatura
from apps.cartoes.services import ResumoFatura, resumir_fatura
from apps.lancamentos.models import Lancamento
from apps.relatorios.services import Totais, totais
from core import dates

RECEITA = Q(tipo=Lancamento.Tipo.RECEITA)
DESPESA = Q(tipo=Lancamento.Tipo.DESPESA)
PENDENTE = Q(status=Lancamento.Status.PENDENTE)


def _no_mes(usuario, mes: date):
    return Lancamento.objects.do_usuario(usuario).filter(
        data__gte=dates.primeiro_dia(mes), data__lte=dates.ultimo_dia(mes))


def resumo_do_mes(usuario, mes: date) -> Totais:
    """Resultado do mês só com o que foi pago; pendentes aparecem à parte."""
    return totais(_no_mes(usuario, mes))


def gastos_por_categoria(usuario, mes: date) -> list[dict]:
    """Despesas do mês agrupadas pela categoria principal, maior primeiro."""
    return list(
        _no_mes(usuario, mes)
        .filter(DESPESA)
        .annotate(grupo=Coalesce("categoria__pai__nome", "categoria__nome"))
        .values("grupo")
        .annotate(total=Sum("valor_centavos"))
        .order_by("-total")
    )


def evolucao_mensal(usuario, ate_mes: date, meses: int = 12) -> list[dict]:
    """Receitas e despesas dos últimos `meses` meses (meses vazios = 0)."""
    inicio = dates.somar_meses(dates.primeiro_dia(ate_mes), -(meses - 1))
    linhas = (
        Lancamento.objects.do_usuario(usuario).filter(data__gte=inicio, data__lte=dates.ultimo_dia(ate_mes))
        .annotate(mes=TruncMonth("data"))
        .values("mes")
        .annotate(receitas=Sum("valor_centavos", filter=RECEITA), despesas=Sum("valor_centavos", filter=DESPESA))
    )
    por_mes = {_como_data(linha["mes"]): linha for linha in linhas}
    return [
        {"mes": mes, "receitas": (por_mes.get(mes) or {}).get("receitas") or 0,
         "despesas": (por_mes.get(mes) or {}).get("despesas") or 0}
        for mes in dates.meses_entre(inicio, ate_mes)
    ]


def _como_data(valor) -> date:
    return valor.date() if hasattr(valor, "date") else valor


@dataclass(frozen=True)
class ContasAVencer:
    lancamentos: list[Lancamento]
    faturas: list[ResumoFatura]


def contas_a_vencer(usuario, dias: int = 30, hoje: date | None = None) -> ContasAVencer:
    """Despesas pendentes (fora do cartão) e faturas em aberto que vencem até
    `dias` à frente, incluindo as atrasadas."""
    hoje = hoje or dates.hoje()
    limite = hoje + timedelta(days=dias)
    lancamentos = list(
        Lancamento.objects.do_usuario(usuario).filter(DESPESA & PENDENTE, fatura__isnull=True, data__lte=limite)
        .select_related("conta", "categoria", "parcelamento")
        .order_by("data")[:50]
    )
    faturas = [
        resumo
        for resumo in map(resumir_fatura, Fatura.objects.do_usuario(usuario).filter(data_vencimento__lte=limite)
                          .select_related("conta").order_by("data_vencimento"))
        if resumo.restante_centavos > 0
    ]
    return ContasAVencer(lancamentos, faturas)
