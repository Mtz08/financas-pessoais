"""Exporta e importa os dados de UM usuário em JSON.

A importação substitui só os dados de quem importa, numa única transação: se o
arquivo tiver qualquer problema, nada muda. Como o banco é compartilhado entre
usuários, os registros importados ganham IDs novos e as ligações entre eles
(conta → lançamento, categoria → subcategoria...) são remapeadas.
"""

import json
import uuid

from django.core import serializers
from django.core.serializers.base import DeserializationError
from django.db import IntegrityError, connection, transaction
from django.db.models import F
from django.utils import timezone

from apps.cartoes.models import Fatura
from apps.categorias.models import Categoria
from apps.contas.models import Conta
from apps.dividas.models import Divida
from apps.lancamentos.models import Lancamento, Parcelamento, Recorrencia
from apps.orcamentos.models import Orcamento
from core.exceptions import RegraDeNegocio

FORMATO = "financas-backup"
VERSAO = 2  # v2: um usuário por arquivo. Arquivos v1 (sistema de um usuário só) continuam aceitos.
VERSOES_ACEITAS = {1, 2}
# Ordem de dependência: quem é referenciado vem antes.
MODELOS = [Conta, Categoria, Fatura, Recorrencia, Parcelamento, Lancamento, Orcamento, Divida]


def exportar(usuario) -> dict:
    return {
        "formato": FORMATO,
        "versao": VERSAO,
        "gerado_em": timezone.now().isoformat(),
        "dados": json.loads(serializers.serialize("json", _registros_em_ordem(usuario))),
    }


def _registros_em_ordem(usuario):
    for modelo in MODELOS:
        # Categorias-raiz (pai NULL) antes das subcategorias, em qualquer banco.
        ordem = [F("pai").asc(nulls_first=True), "pk"] if modelo is Categoria else ["pk"]
        yield from modelo.objects.do_usuario(usuario).order_by(*ordem)


@transaction.atomic
def importar(usuario, conteudo: bytes) -> dict[str, int]:
    pacote = _ler_pacote(conteudo)
    apagar_dados_do_usuario(usuario)
    contagem = {modelo._meta.verbose_name_plural: 0 for modelo in MODELOS}
    religador = _Religador(usuario)
    try:
        for registro in serializers.deserialize("json", json.dumps(pacote["dados"])):
            objeto = registro.object
            _validar_modelo(objeto)
            id_antigo = objeto.pk
            religador.religar(objeto)
            objeto.pk = None
            objeto.save(force_insert=True)
            religador.registrar(objeto, id_antigo)
            contagem[objeto._meta.verbose_name_plural] += 1
        # FKs são verificadas só no commit (DEFERRED); força a checagem aqui
        # para que uma referência quebrada vire erro tratado e rollback.
        connection.check_constraints(table_names=[m._meta.db_table for m in MODELOS])
    except (DeserializationError, IntegrityError, KeyError, ValueError) as erro:
        raise RegraDeNegocio(f"Arquivo de backup inválido: {erro}") from erro
    return contagem


class _Religador:
    """Troca os IDs antigos do arquivo pelos IDs novos gerados nesta importação."""

    def __init__(self, usuario):
        self.usuario = usuario
        self.novos_ids: dict[type, dict[int, int]] = {modelo: {} for modelo in MODELOS}
        self.transferencias: dict[uuid.UUID, uuid.UUID] = {}

    def religar(self, objeto) -> None:
        for campo in objeto._meta.concrete_fields:
            if campo.is_relation:
                self._religar_chave(objeto, campo)
        if isinstance(objeto, Lancamento) and objeto.transferencia_id:
            # O par saída/entrada ganha um identificador novo (o antigo pode existir em outra conta).
            objeto.transferencia_id = self.transferencias.setdefault(objeto.transferencia_id, uuid.uuid4())

    def _religar_chave(self, objeto, campo) -> None:
        if campo.name == "dono":
            setattr(objeto, campo.attname, self.usuario.pk)
            return
        id_antigo = getattr(objeto, campo.attname)
        if id_antigo is None:
            return
        mapa = self.novos_ids.get(campo.related_model)
        if mapa is None or id_antigo not in mapa:
            raise RegraDeNegocio(
                f"Backup inconsistente: um registro de {objeto._meta.verbose_name_plural} aponta para "
                f"{campo.related_model._meta.verbose_name} que não está no arquivo."
            )
        setattr(objeto, campo.attname, mapa[id_antigo])

    def registrar(self, objeto, id_antigo: int) -> None:
        self.novos_ids[type(objeto)][id_antigo] = objeto.pk


def _ler_pacote(conteudo: bytes) -> dict:
    try:
        pacote = json.loads(conteudo.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise RegraDeNegocio("O arquivo não é um JSON válido.") from erro
    if not isinstance(pacote, dict) or pacote.get("formato") != FORMATO:
        raise RegraDeNegocio("Este arquivo não é um backup deste sistema.")
    if pacote.get("versao") not in VERSOES_ACEITAS:
        raise RegraDeNegocio(f"Versão de backup não suportada: {pacote.get('versao')}.")
    if not isinstance(pacote.get("dados"), list):
        raise RegraDeNegocio("Backup sem a lista de dados.")
    return pacote


def _validar_modelo(objeto) -> None:
    """Só aceita as tabelas de finanças: um JSON adulterado não consegue
    criar usuários nem mexer em outras tabelas."""
    if type(objeto) not in MODELOS:
        raise RegraDeNegocio(f"Tabela não permitida no backup: {objeto._meta.label}.")


def apagar_dados_do_usuario(usuario) -> None:
    """Remove só os dados deste usuário, na ordem que respeita as ligações."""
    Lancamento.objects.do_usuario(usuario).delete()
    Orcamento.objects.do_usuario(usuario).delete()
    Parcelamento.objects.do_usuario(usuario).delete()
    Recorrencia.objects.do_usuario(usuario).delete()
    Fatura.objects.do_usuario(usuario).delete()
    Categoria.objects.do_usuario(usuario).filter(pai__isnull=False).delete()
    Categoria.objects.do_usuario(usuario).delete()
    Conta.objects.do_usuario(usuario).delete()
    Divida.objects.do_usuario(usuario).delete()
