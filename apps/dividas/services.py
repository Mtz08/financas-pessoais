from dataclasses import dataclass
from datetime import date

from django.db.models import Count, Sum

from core import dates

from .models import Divida


def dar_baixa(divida: Divida, data: date | None = None) -> Divida:
    divida.paga = True
    divida.data_pagamento = data or dates.hoje()
    divida.save(update_fields=["paga", "data_pagamento", "atualizado_em"])
    return divida


def reabrir(divida: Divida) -> Divida:
    divida.paga = False
    divida.data_pagamento = None
    divida.save(update_fields=["paga", "data_pagamento", "atualizado_em"])
    return divida


@dataclass(frozen=True)
class GrupoMes:
    mes: date | None  # dia 1º do mês de vencimento; None = sem vencimento
    dividas: list[Divida]

    @property
    def total(self) -> int:
        return sum(d.valor_centavos for d in self.dividas)


def agrupar_por_mes(dividas) -> list[GrupoMes]:
    """Agrupa pelo mês de vencimento, do mais antigo ao mais novo;
    as sem vencimento vão para um grupo no final."""
    grupos: dict[date | None, list[Divida]] = {}
    for divida in dividas:
        chave = dates.primeiro_dia(divida.vencimento) if divida.vencimento else None
        grupos.setdefault(chave, []).append(divida)
    ordem = sorted(grupos, key=lambda mes: (mes is None, mes or date.min))
    return [GrupoMes(mes, grupos[mes]) for mes in ordem]


@dataclass(frozen=True)
class ResumoDividas:
    total_aberto: int
    quantidade_aberta: int
    vencidas: int
    por_credor: list[dict]


def resumir(hoje: date | None = None) -> ResumoDividas:
    hoje = hoje or dates.hoje()
    abertas = Divida.objects.filter(paga=False)
    somas = abertas.aggregate(total=Sum("valor_centavos"), qtd=Count("id"))
    por_credor = list(
        abertas.values("credor").annotate(total=Sum("valor_centavos"), qtd=Count("id")).order_by("-total")
    )
    return ResumoDividas(
        total_aberto=somas["total"] or 0,
        quantidade_aberta=somas["qtd"] or 0,
        vencidas=abertas.filter(vencimento__lt=hoje).count(),
        por_credor=por_credor,
    )
