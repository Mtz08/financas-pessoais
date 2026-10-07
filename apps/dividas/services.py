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
    mes: date  # dia 1º do mês da data da dívida ("Desde")
    dividas: list[Divida]

    @property
    def total(self) -> int:
        return sum(d.valor_centavos for d in self.dividas)


def agrupar_por_mes(dividas) -> list[GrupoMes]:
    """Agrupa pelo mês da data da dívida (campo "Desde"), do mais antigo ao mais novo."""
    grupos: dict[date, list[Divida]] = {}
    for divida in sorted(dividas, key=lambda d: (d.data, d.id)):
        grupos.setdefault(dates.primeiro_dia(divida.data), []).append(divida)
    return [GrupoMes(mes, grupos[mes]) for mes in sorted(grupos)]


@dataclass(frozen=True)
class ResumoDividas:
    total_aberto: int
    quantidade_aberta: int
    vencidas: int
    por_credor: list[dict]


def resumir(usuario, hoje: date | None = None) -> ResumoDividas:
    hoje = hoje or dates.hoje()
    abertas = Divida.objects.do_usuario(usuario).filter(paga=False)
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
