"""Compra parcelada: um cabeçalho (Parcelamento) + N lançamentos."""

from django.db import transaction

from apps.cartoes.services import competencia_da_compra, obter_fatura
from apps.lancamentos.models import Lancamento, Parcelamento
from core import dates
from core.exceptions import RegraDeNegocio
from core.money import ValorInvalido, dividir_em_parcelas

from .dados import DadosLancamento, DadosParcelamento, Escopo
from .lancamentos import atualizar_lancamento, criar_lancamento
from .validacao import validar_categoria, validar_conta_ativa


@transaction.atomic
def criar_parcelamento(dados: DadosParcelamento) -> Parcelamento:
    """Parcela i vence i meses após a compra. No cartão, cada parcela vai
    para a fatura seguinte à anterior (a 1ª respeita o dia de fechamento)."""
    validar_conta_ativa(dados.conta)
    validar_categoria(dados.categoria, Lancamento.Tipo.DESPESA)
    valores = _dividir(dados)
    parcelamento = Parcelamento.objects.create(
        descricao=dados.descricao.strip(),
        conta=dados.conta,
        categoria=dados.categoria,
        valor_total_centavos=dados.valor_total_centavos,
        quantidade_parcelas=dados.quantidade_parcelas,
        data_compra=dados.data_compra,
    )
    for indice, valor in enumerate(valores):
        _criar_parcela(parcelamento, indice, valor)
    return parcelamento


def _dividir(dados: DadosParcelamento) -> list[int]:
    if not 2 <= dados.quantidade_parcelas <= 72:
        raise RegraDeNegocio("O parcelamento deve ter de 2 a 72 parcelas.")
    try:
        return dividir_em_parcelas(dados.valor_total_centavos, dados.quantidade_parcelas)
    except ValorInvalido as erro:
        raise RegraDeNegocio(str(erro)) from erro


def _criar_parcela(parcelamento: Parcelamento, indice: int, valor: int) -> Lancamento:
    conta = parcelamento.conta
    fatura = None
    if conta.eh_cartao:
        primeira = competencia_da_compra(conta, parcelamento.data_compra)
        fatura = obter_fatura(conta, dates.somar_meses(primeira, indice))
    dados = DadosLancamento(
        tipo=Lancamento.Tipo.DESPESA,
        conta=conta,
        categoria=parcelamento.categoria,
        descricao=parcelamento.descricao,
        valor_centavos=valor,
        data=dates.somar_meses(parcelamento.data_compra, indice),
    )
    return criar_lancamento(dados, fatura=fatura, parcelamento=parcelamento, numero_parcela=indice + 1)


def _parcelas_no_escopo(lancamento: Lancamento, escopo: Escopo):
    parcelas = lancamento.parcelamento.parcelas.all()
    if escopo == Escopo.ESTA:
        return parcelas.filter(pk=lancamento.pk)
    if escopo == Escopo.ESTA_E_PROXIMAS:
        return parcelas.filter(numero_parcela__gte=lancamento.numero_parcela)
    return parcelas


@transaction.atomic
def editar_parcela(lancamento: Lancamento, dados: DadosLancamento, escopo: Escopo) -> None:
    """"Somente esta" aceita qualquer campo. Nas demais, data e conta ficam
    fixas por parcela (cada uma já está na sua fatura)."""
    if escopo == Escopo.ESTA:
        atualizar_lancamento(lancamento, dados)
        return
    if dados.conta.pk != lancamento.conta_id:
        raise RegraDeNegocio("Para trocar a conta de várias parcelas, exclua e lance a compra novamente.")
    for parcela in _parcelas_no_escopo(lancamento, escopo):
        status = dados.status if parcela.pk == lancamento.pk else parcela.status
        atualizar_lancamento(parcela, dados.com(data=parcela.data, status=status))
    if escopo == Escopo.TODAS:
        _atualizar_cabecalho(lancamento.parcelamento, dados)


def _atualizar_cabecalho(parcelamento: Parcelamento, dados: DadosLancamento) -> None:
    parcelamento.descricao = dados.descricao.strip()
    parcelamento.categoria = dados.categoria
    parcelamento.save(update_fields=["descricao", "categoria", "atualizado_em"])


@transaction.atomic
def excluir_parcela(lancamento: Lancamento, escopo: Escopo) -> None:
    parcelamento = lancamento.parcelamento
    _parcelas_no_escopo(lancamento, escopo).delete()
    if not parcelamento.parcelas.exists():
        parcelamento.delete()
