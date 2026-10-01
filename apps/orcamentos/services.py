from dataclasses import dataclass
from datetime import date

from django.db.models import Q, Sum

from apps.categorias.models import Categoria
from apps.lancamentos.models import Lancamento
from core import dates

from .models import Orcamento

PERCENTUAL_ALERTA = 80
PERCENTUAL_LIMITE = 100


@dataclass(frozen=True)
class SituacaoOrcamento:
    categoria: Categoria
    limite_centavos: int
    gasto_centavos: int

    @property
    def percentual(self) -> int:
        return self.gasto_centavos * 100 // self.limite_centavos

    @property
    def nivel(self) -> str:
        if self.percentual >= PERCENTUAL_LIMITE:
            return "estourado"
        if self.percentual >= PERCENTUAL_ALERTA:
            return "alerta"
        return "ok"

    @property
    def restante_centavos(self) -> int:
        return self.limite_centavos - self.gasto_centavos


def limites_vigentes(mes: date) -> dict[int, Orcamento]:
    """Para cada categoria, o orçamento com maior `vigente_desde` <= mês."""
    vigentes: dict[int, Orcamento] = {}
    consulta = (
        Orcamento.objects.filter(vigente_desde__lte=dates.primeiro_dia(mes), categoria__ativo=True)
        .select_related("categoria", "categoria__pai")
        .order_by("categoria_id", "-vigente_desde")
    )
    for orcamento in consulta:
        vigentes.setdefault(orcamento.categoria_id, orcamento)
    return vigentes


def gasto_no_mes(categoria: Categoria, mes: date) -> int:
    """Despesas da categoria e das suas subcategorias no mês (pagas ou não)."""
    total = Lancamento.objects.filter(
        Q(categoria=categoria) | Q(categoria__pai=categoria),
        tipo=Lancamento.Tipo.DESPESA,
        data__gte=dates.primeiro_dia(mes),
        data__lte=dates.ultimo_dia(mes),
    ).aggregate(total=Sum("valor_centavos"))["total"]
    return total or 0


def situacao_do_mes(mes: date) -> list[SituacaoOrcamento]:
    situacoes = [
        SituacaoOrcamento(o.categoria, o.limite_centavos, gasto_no_mes(o.categoria, mes))
        for o in limites_vigentes(mes).values()
    ]
    return sorted(situacoes, key=lambda s: s.percentual, reverse=True)


def alertas_do_mes(mes: date) -> list[SituacaoOrcamento]:
    return [s for s in situacao_do_mes(mes) if s.nivel != "ok"]
