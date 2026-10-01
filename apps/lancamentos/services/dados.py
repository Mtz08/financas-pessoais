"""Objetos de entrada dos serviços (independentes de formulário ou HTTP)."""

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from apps.categorias.models import Categoria
from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento


class Escopo(StrEnum):
    ESTA = "ESTA"
    ESTA_E_PROXIMAS = "ESTA_E_PROXIMAS"
    TODAS = "TODAS"


ESCOPO_ROTULOS = {
    Escopo.ESTA: "Somente esta",
    Escopo.ESTA_E_PROXIMAS: "Esta e as próximas",
    Escopo.TODAS: "Todas",
}


@dataclass(frozen=True)
class DadosLancamento:
    tipo: str  # RECEITA | DESPESA
    conta: Conta
    categoria: Categoria
    descricao: str
    valor_centavos: int
    data: date
    status: str = Lancamento.Status.PENDENTE

    def com(self, **alteracoes) -> "DadosLancamento":
        return replace(self, **alteracoes)

    @classmethod
    def de_lancamento(cls, lancamento: Lancamento) -> "DadosLancamento":
        return cls(
            tipo=lancamento.tipo,
            conta=lancamento.conta,
            categoria=lancamento.categoria,
            descricao=lancamento.descricao,
            valor_centavos=lancamento.valor_centavos,
            data=lancamento.data,
            status=lancamento.status,
        )


@dataclass(frozen=True)
class DadosTransferencia:
    origem: Conta
    destino: Conta
    valor_centavos: int
    data: date
    descricao: str = "Transferência"
    status: str = Lancamento.Status.PAGO


@dataclass(frozen=True)
class DadosParcelamento:
    conta: Conta
    categoria: Categoria
    descricao: str
    valor_total_centavos: int
    quantidade_parcelas: int
    data_compra: date
