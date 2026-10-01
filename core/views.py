"""Fluxo comum dos formulários: validar -> executar em transação -> redirecionar."""

from collections.abc import Callable

from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from core.exceptions import EnvioDuplicado, RegraDeNegocio
from core.idempotencia import consumir_chave


def processar_formulario(
    request: HttpRequest,
    form,
    acao: Callable[[object], object],
    *,
    sucesso: str,
    template: str,
    contexto: dict | None = None,
    mensagem: str = "Registro salvo.",
) -> HttpResponse:
    """Executa `acao(form)` numa transação (com a chave de idempotência).

    - Envio duplicado: não faz nada e avisa.
    - RegraDeNegocio: desfaz tudo e mostra o erro no formulário.
    """
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                if "chave" in form.cleaned_data:
                    consumir_chave(form.cleaned_data["chave"])
                acao(form)
        except EnvioDuplicado:
            messages.info(request, "Este formulário já tinha sido enviado; nada foi duplicado.")
            return redirect(sucesso)
        except RegraDeNegocio as erro:
            form.add_error(None, str(erro))
        else:
            messages.success(request, mensagem)
            return redirect(sucesso)
    return render(request, template, {"form": form, **(contexto or {})})


def excluir_ou_avisar(request: HttpRequest, objeto, sucesso: str) -> HttpResponse:
    """Exclui; se houver lançamentos ligados (PROTECT), sugere arquivar."""
    try:
        with transaction.atomic():
            objeto.delete()
        messages.success(request, f"“{objeto}” excluído.")
    except ProtectedError:
        messages.error(request, f"“{objeto}” tem lançamentos vinculados e não pode ser excluído. Arquive-o.")
    return redirect(sucesso)
