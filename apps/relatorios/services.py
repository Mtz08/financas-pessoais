import csv
from dataclasses import dataclass
from datetime import date
from typing import IO

from django.db.models import Q, QuerySet, Sum

from apps.categorias.models import Categoria
from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento
from core.money import centavos_para_reais

# Células que começam com estes caracteres viram fórmula no Excel (CSV injection).
_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class FiltroRelatorio:
    inicio: date
    fim: date
    conta: Conta | None = None
    categoria: Categoria | None = None
    tipo: str | None = None


@dataclass(frozen=True)
class Totais:
    receitas: int
    despesas: int

    @property
    def resultado(self) -> int:
        return self.receitas - self.despesas


def filtrar(filtro: FiltroRelatorio) -> QuerySet[Lancamento]:
    consulta = Lancamento.objects.filter(data__gte=filtro.inicio, data__lte=filtro.fim).select_related(
        "conta", "categoria", "categoria__pai", "parcelamento"
    )
    if filtro.conta:
        consulta = consulta.filter(conta=filtro.conta)
    if filtro.categoria:  # inclui as subcategorias
        consulta = consulta.filter(Q(categoria=filtro.categoria) | Q(categoria__pai=filtro.categoria))
    if filtro.tipo:
        consulta = consulta.filter(tipo=filtro.tipo)
    return consulta.order_by("data", "id")


def totais(consulta: QuerySet[Lancamento]) -> Totais:
    """Transferências não entram: não são receita nem despesa."""
    somas = consulta.aggregate(
        receitas=Sum("valor_centavos", filter=Q(tipo=Lancamento.Tipo.RECEITA)),
        despesas=Sum("valor_centavos", filter=Q(tipo=Lancamento.Tipo.DESPESA)),
    )
    return Totais(somas["receitas"] or 0, somas["despesas"] or 0)


def escrever_csv(consulta: QuerySet[Lancamento], destino: IO[str]) -> None:
    """CSV no padrão do Excel pt-BR: separador ';' e vírgula decimal."""
    escritor = csv.writer(destino, delimiter=";")
    escritor.writerow(["Data", "Tipo", "Conta", "Categoria", "Descrição", "Valor", "Status"])
    for lancamento in consulta:
        escritor.writerow(
            [
                f"{lancamento.data:%d/%m/%Y}",
                lancamento.get_tipo_display(),
                _seguro(str(lancamento.conta)),
                _seguro(str(lancamento.categoria or "")),
                _seguro(lancamento.descricao_completa),
                centavos_para_reais(lancamento.valor_com_sinal, simbolo=False),
                lancamento.get_status_display(),
            ]
        )


def _seguro(texto: str) -> str:
    return f"'{texto}" if texto.startswith(_INICIO_DE_FORMULA) else texto
