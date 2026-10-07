"""Modelos compartilhados por todos os apps."""

from django.db import models


class ModeloComDatas(models.Model):
    """Base abstrata: timestamps gravados em UTC (USE_TZ=True)."""

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ModeloArquivavel(ModeloComDatas):
    """Registro que não pode ser excluído quando já tem histórico: é arquivado."""

    ativo = models.BooleanField(default=True)

    class Meta:
        abstract = True


class ChaveIdempotencia(models.Model):
    """Cada formulário envia um UUID único; o segundo envio igual é recusado.

    Protege contra duplo clique e reenvio (F5) de formulários.
    """

    chave = models.UUIDField(unique=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "chave de idempotência"
        verbose_name_plural = "chaves de idempotência"

    def __str__(self):
        return str(self.chave)


def gerenciador_do_dono(caminho_dono: str):
    """Manager com `.do_usuario(usuario)`, que filtra pelo dono do registro.

    `caminho_dono` é o lookup até o usuário: "dono" para Conta/Categoria/Dívida,
    "conta__dono" para o que pertence a uma conta, "categoria__dono" para orçamento.
    Toda consulta feita a partir de uma requisição deve começar por aqui.
    """

    class QuerySetDoDono(models.QuerySet):
        def do_usuario(self, usuario):
            return self.filter(**{caminho_dono: usuario})

    return QuerySetDoDono.as_manager()
