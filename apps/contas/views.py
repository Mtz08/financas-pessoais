from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.lancamentos.services.saldos import saldos_das_contas, saldo_conta
from apps.contas.models import Conta
from core.views import excluir_ou_avisar, processar_formulario

from .forms import ContaForm


def lista(request):
    ativas = saldos_das_contas()
    arquivadas = Conta.objects.filter(ativo=False)
    return render(request, "contas/lista.html", {
        "ativas": ativas,
        "arquivadas": [(conta, saldo_conta(conta)) for conta in arquivadas],
    })


def nova(request):
    form = ContaForm(request.POST or None)
    return processar_formulario(request, form, lambda f: f.save(), sucesso="contas:lista",
                                template="form.html", contexto={"titulo": "Nova conta"}, mensagem="Conta criada.")


def editar(request, pk):
    conta = get_object_or_404(Conta, pk=pk)
    form = ContaForm(request.POST or None, instance=conta)
    return processar_formulario(request, form, lambda f: f.save(), sucesso="contas:lista",
                                template="form.html", contexto={"titulo": f"Editar {conta}"})


@require_POST
def arquivar(request, pk):
    conta = get_object_or_404(Conta, pk=pk)
    conta.ativo = not conta.ativo
    conta.save(update_fields=["ativo", "atualizado_em"])
    messages.success(request, f"Conta “{conta}” {'reativada' if conta.ativo else 'arquivada'}.")
    return redirect("contas:lista")


@require_POST
def excluir(request, pk):
    return excluir_ou_avisar(request, get_object_or_404(Conta, pk=pk), "contas:lista")
