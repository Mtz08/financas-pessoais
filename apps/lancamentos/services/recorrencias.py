"""Lançamentos fixos mensais gerados a partir de um molde (Recorrencia).

A geração é idempotente: UNIQUE (recorrencia, competencia) + `gerada_ate`
que só avança. Rodar duas vezes não duplica, e excluir uma ocorrência
não faz ela voltar.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q

from apps.categorias.models import Categoria
from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento, Recorrencia
from core import dates
from core.exceptions import RegraDeNegocio

from .dados import DadosLancamento, Escopo
from .lancamentos import atualizar_lancamento, criar_lancamento
from .validacao import validar_categoria, validar_conta_ativa, validar_mesmo_dono, validar_valor

HORIZONTE_MESES = 2  # gera o mês atual + 2 à frente (para "contas a vencer")


@dataclass(frozen=True)
class DadosRecorrencia:
    tipo: str
    conta: Conta
    categoria: Categoria
    descricao: str
    valor_centavos: int
    dia: int
    data_inicio: date
    data_fim: date | None = None


def horizonte_padrao() -> date:
    return dates.ultimo_dia(dates.somar_meses(dates.hoje(), HORIZONTE_MESES))


@transaction.atomic
def criar_recorrencia(dados: DadosRecorrencia) -> Recorrencia:
    _validar(dados)
    recorrencia = Recorrencia.objects.create(**dados.__dict__)
    gerar_lancamentos(recorrencia)
    return recorrencia


def _validar(dados: DadosRecorrencia) -> None:
    validar_mesmo_dono(dados.conta, dados.categoria)
    validar_conta_ativa(dados.conta)
    validar_categoria(dados.categoria, dados.tipo)
    validar_valor(dados.valor_centavos)
    if not 1 <= dados.dia <= 31:
        raise RegraDeNegocio("O dia deve estar entre 1 e 31.")
    if dados.data_fim and dados.data_fim < dados.data_inicio:
        raise RegraDeNegocio("A data final deve ser posterior à inicial.")


def gerar_todas(ate: date | None = None) -> int:
    """Gera as ocorrências pendentes de todas as recorrências vigentes."""
    ate = ate or horizonte_padrao()
    vigentes = Recorrencia.objects.filter(
        Q(gerada_ate__isnull=True) | Q(gerada_ate__lt=dates.primeiro_dia(ate)),
        conta__ativo=True,
        categoria__ativo=True,
        data_inicio__lte=ate,
    )
    return sum(len(gerar_lancamentos(rec, ate)) for rec in vigentes)


@transaction.atomic
def gerar_lancamentos(recorrencia: Recorrencia, ate: date | None = None) -> list[Lancamento]:
    recorrencia = Recorrencia.objects.select_for_update().get(pk=recorrencia.pk)
    ate = min(ate or horizonte_padrao(), recorrencia.data_fim or date.max)
    inicio = (
        dates.somar_meses(recorrencia.gerada_ate, 1) if recorrencia.gerada_ate else recorrencia.data_inicio
    )
    criados = [
        _criar_ocorrencia(recorrencia, competencia)
        for competencia in dates.meses_entre(inicio, ate)
        if recorrencia.data_inicio <= _data_da_ocorrencia(recorrencia, competencia) <= ate
    ]
    if inicio <= ate:
        recorrencia.gerada_ate = dates.primeiro_dia(ate)
        recorrencia.save(update_fields=["gerada_ate", "atualizado_em"])
    return criados


def _data_da_ocorrencia(recorrencia: Recorrencia, competencia: date) -> date:
    return dates.data_no_mes(competencia.year, competencia.month, recorrencia.dia)


def _criar_ocorrencia(recorrencia: Recorrencia, competencia: date) -> Lancamento:
    dados = DadosLancamento(
        tipo=recorrencia.tipo,
        conta=recorrencia.conta,
        categoria=recorrencia.categoria,
        descricao=recorrencia.descricao,
        valor_centavos=recorrencia.valor_centavos,
        data=_data_da_ocorrencia(recorrencia, competencia),
    )
    return criar_lancamento(dados, recorrencia=recorrencia, competencia_recorrencia=competencia)


# --- Edição e exclusão por escopo -----------------------------------------


@transaction.atomic
def editar_ocorrencia(lancamento: Lancamento, dados: DadosLancamento, escopo: Escopo) -> None:
    """Somente esta: altera só o lançamento.
    Esta e as próximas: encerra o molde no mês anterior e cria um novo.
    Todas: altera o molde. Ocorrências já PAGAS de outros meses ficam
    intactas (são histórico)."""
    if escopo == Escopo.ESTA:
        atualizar_lancamento(lancamento, dados)
        return
    recorrencia = _molde_para_alterar(lancamento, escopo)
    _aplicar_no_molde(recorrencia, dados)
    for ocorrencia in _ocorrencias_afetadas(recorrencia, lancamento):
        atualizar_lancamento(ocorrencia, _dados_da_ocorrencia(recorrencia, ocorrencia, lancamento, dados))


def _molde_para_alterar(lancamento: Lancamento, escopo: Escopo) -> Recorrencia:
    recorrencia = lancamento.recorrencia
    competencia = lancamento.competencia_recorrencia
    if escopo == Escopo.TODAS or competencia <= dates.primeiro_dia(recorrencia.data_inicio):
        return recorrencia
    return _dividir_recorrencia(recorrencia, competencia)


def _dividir_recorrencia(recorrencia: Recorrencia, competencia: date) -> Recorrencia:
    nova = Recorrencia.objects.create(
        tipo=recorrencia.tipo,
        conta=recorrencia.conta,
        categoria=recorrencia.categoria,
        descricao=recorrencia.descricao,
        valor_centavos=recorrencia.valor_centavos,
        dia=recorrencia.dia,
        data_inicio=competencia,
        data_fim=recorrencia.data_fim,
        gerada_ate=recorrencia.gerada_ate,
    )
    recorrencia.lancamentos.filter(competencia_recorrencia__gte=competencia).update(recorrencia=nova)
    recorrencia.data_fim = competencia - timedelta(days=1)
    recorrencia.save(update_fields=["data_fim", "atualizado_em"])
    return nova


def _aplicar_no_molde(recorrencia: Recorrencia, dados: DadosLancamento) -> None:
    validar_valor(dados.valor_centavos)
    recorrencia.conta = dados.conta
    recorrencia.categoria = dados.categoria
    recorrencia.descricao = dados.descricao.strip()
    recorrencia.valor_centavos = dados.valor_centavos
    recorrencia.dia = dados.data.day
    recorrencia.save()


def _ocorrencias_afetadas(recorrencia: Recorrencia, lancamento: Lancamento):
    return recorrencia.lancamentos.filter(Q(status=Lancamento.Status.PENDENTE) | Q(pk=lancamento.pk))


def _dados_da_ocorrencia(recorrencia, ocorrencia, editado, dados: DadosLancamento) -> DadosLancamento:
    if ocorrencia.pk == editado.pk:
        return dados
    data = _data_da_ocorrencia(recorrencia, ocorrencia.competencia_recorrencia)
    return dados.com(data=data, status=ocorrencia.status)


@transaction.atomic
def excluir_ocorrencia(lancamento: Lancamento, escopo: Escopo) -> None:
    recorrencia = lancamento.recorrencia
    if escopo == Escopo.ESTA:
        lancamento.delete()
        return
    pendentes = recorrencia.lancamentos.filter(status=Lancamento.Status.PENDENTE)
    if escopo == Escopo.ESTA_E_PROXIMAS:
        pendentes = pendentes.filter(competencia_recorrencia__gte=lancamento.competencia_recorrencia)
    pendentes.delete()
    Lancamento.objects.filter(pk=lancamento.pk).delete()
    if escopo == Escopo.TODAS:
        recorrencia.delete()  # ocorrências pagas ficam, com recorrencia = NULL
    else:
        encerrar_recorrencia(recorrencia, lancamento.competencia_recorrencia - timedelta(days=1))


def encerrar_recorrencia(recorrencia: Recorrencia, data_fim: date) -> None:
    """Para de gerar a partir de `data_fim`. Se acabaria antes de começar, exclui."""
    if data_fim < recorrencia.data_inicio:
        recorrencia.lancamentos.filter(status=Lancamento.Status.PENDENTE).delete()
        recorrencia.delete()
        return
    recorrencia.lancamentos.filter(status=Lancamento.Status.PENDENTE, data__gt=data_fim).delete()
    recorrencia.data_fim = data_fim
    recorrencia.save(update_fields=["data_fim", "atualizado_em"])
