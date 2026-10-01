"""Exporta e importa todos os dados em JSON.

A importação SUBSTITUI tudo, dentro de uma única transação: se o arquivo
tiver qualquer problema, o banco volta exatamente ao estado anterior.
"""

import json

from django.core import serializers
from django.core.management.color import no_style
from django.core.serializers.base import DeserializationError
from django.db import IntegrityError, connection, transaction
from django.db.models import F
from django.utils import timezone

from apps.cartoes.models import Fatura
from apps.categorias.models import Categoria
from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento, Parcelamento, Recorrencia
from apps.orcamentos.models import Orcamento
from core.exceptions import RegraDeNegocio

FORMATO = "financas-backup"
VERSAO = 1
# Ordem de dependência: quem é referenciado vem antes.
MODELOS = [Conta, Categoria, Fatura, Recorrencia, Parcelamento, Lancamento, Orcamento]


def exportar() -> dict:
    return {
        "formato": FORMATO,
        "versao": VERSAO,
        "gerado_em": timezone.now().isoformat(),
        "dados": json.loads(serializers.serialize("json", _registros_em_ordem())),
    }


def _registros_em_ordem():
    for modelo in MODELOS:
        # Categorias-raiz (pai NULL) antes das subcategorias, em qualquer banco.
        ordem = [F("pai").asc(nulls_first=True), "pk"] if modelo is Categoria else ["pk"]
        yield from modelo.objects.order_by(*ordem)


@transaction.atomic
def importar(conteudo: bytes) -> dict[str, int]:
    pacote = _ler_pacote(conteudo)
    apagar_tudo()
    contagem = {modelo._meta.verbose_name_plural: 0 for modelo in MODELOS}
    try:
        for registro in serializers.deserialize("json", json.dumps(pacote["dados"])):
            _validar_modelo(registro.object)
            registro.save()
            contagem[registro.object._meta.verbose_name_plural] += 1
        # FKs são verificadas só no commit (DEFERRED); força a checagem aqui
        # para que uma referência quebrada vire erro tratado e rollback.
        connection.check_constraints(table_names=[m._meta.db_table for m in MODELOS])
    except (DeserializationError, IntegrityError, KeyError, ValueError) as erro:
        raise RegraDeNegocio(f"Arquivo de backup inválido: {erro}") from erro
    _reiniciar_sequencias()
    return contagem


def _ler_pacote(conteudo: bytes) -> dict:
    try:
        pacote = json.loads(conteudo.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise RegraDeNegocio("O arquivo não é um JSON válido.") from erro
    if not isinstance(pacote, dict) or pacote.get("formato") != FORMATO:
        raise RegraDeNegocio("Este arquivo não é um backup deste sistema.")
    if pacote.get("versao") != VERSAO:
        raise RegraDeNegocio(f"Versão de backup não suportada: {pacote.get('versao')}.")
    if not isinstance(pacote.get("dados"), list):
        raise RegraDeNegocio("Backup sem a lista de dados.")
    return pacote


def _validar_modelo(objeto) -> None:
    """Só aceita as tabelas de finanças: um JSON adulterado não consegue
    criar usuários nem mexer em outras tabelas."""
    if type(objeto) not in MODELOS:
        raise RegraDeNegocio(f"Tabela não permitida no backup: {objeto._meta.label}.")


def apagar_tudo() -> None:
    Lancamento.objects.all().delete()
    Orcamento.objects.all().delete()
    Parcelamento.objects.all().delete()
    Recorrencia.objects.all().delete()
    Fatura.objects.all().delete()
    Categoria.objects.filter(pai__isnull=False).delete()
    Categoria.objects.all().delete()
    Conta.objects.all().delete()


def _reiniciar_sequencias() -> None:
    """No PostgreSQL, ajusta os contadores de ID após inserir IDs explícitos."""
    comandos = connection.ops.sequence_reset_sql(no_style(), MODELOS)
    with connection.cursor() as cursor:
        for sql in comandos:
            cursor.execute(sql)
