import uuid

from django.db import IntegrityError, transaction

from core.exceptions import EnvioDuplicado
from core.models import ChaveIdempotencia


def consumir_chave(chave: uuid.UUID) -> None:
    """Registra a chave do formulário; se já existir, é envio duplicado.

    Deve rodar na MESMA transação da operação: se a operação falhar,
    o rollback libera a chave e o usuário pode corrigir e reenviar.
    """
    try:
        with transaction.atomic():
            ChaveIdempotencia.objects.create(chave=chave)
    except IntegrityError as erro:
        raise EnvioDuplicado("Este formulário já foi enviado.") from erro
