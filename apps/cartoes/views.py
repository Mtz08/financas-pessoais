from django import forms
from django.shortcuts import get_object_or_404, redirect, render

from apps.contas.models import Conta
from apps.lancamentos.forms import contas_ativas
from core import dates
from core.forms import CampoData, CampoReais, FormIdempotente
from core.views import processar_formulario

from .models import Fatura
from .pagamentos import pagar_fatura
from .services import fatura_da_compra, resumir_fatura


class PagamentoForm(FormIdempotente):
    conta_origem = forms.ModelChoiceField(queryset=Conta.objects.none(), label="Pagar com")
    valor = CampoReais(label="Valor (R$)")
    data = CampoData(label="Data do pagamento")

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["conta_origem"].queryset = contas_ativas(usuario, sem_cartao=True)
        self.fields["data"].initial = dates.hoje()


def faturas(request, conta_pk):
    cartao = get_object_or_404(Conta.objects.do_usuario(request.user), pk=conta_pk, tipo=Conta.Tipo.CARTAO)
    fatura_da_compra(cartao, dates.hoje())  # garante que a fatura corrente exista
    resumos = [resumir_fatura(f) for f in cartao.faturas.order_by("-competencia")]
    return render(request, "cartoes/faturas.html", {"cartao": cartao, "resumos": resumos,
                                                    "cartoes": Conta.objects.do_usuario(request.user).filter(tipo=Conta.Tipo.CARTAO)})


def fatura(request, pk):
    fatura = get_object_or_404(Fatura.objects.do_usuario(request.user).select_related("conta"), pk=pk)
    resumo = resumir_fatura(fatura)
    form = PagamentoForm(request.POST or None, usuario=request.user, initial={"valor": resumo.restante_centavos or None})
    if request.method == "POST":
        return processar_formulario(
            request, form,
            lambda f: pagar_fatura(fatura, f.cleaned_data["conta_origem"], f.cleaned_data["valor"],
                                   f.cleaned_data["data"]),
            sucesso=request.path, template="cartoes/fatura.html",
            contexto=_contexto_fatura(fatura, resumo), mensagem="Pagamento registrado.",
        )
    return render(request, "cartoes/fatura.html", {"form": form, **_contexto_fatura(fatura, resumo)})


def _contexto_fatura(fatura: Fatura, resumo) -> dict:
    lancamentos = fatura.lancamentos.select_related("categoria", "categoria__pai", "parcelamento").order_by("data")
    return {"fatura": fatura, "resumo": resumo, "lancamentos": lancamentos}


def cartoes(request):
    primeiro = Conta.objects.do_usuario(request.user).filter(tipo=Conta.Tipo.CARTAO, ativo=True).first()
    if primeiro:
        return redirect("cartoes:faturas", conta_pk=primeiro.pk)
    return render(request, "cartoes/faturas.html", {"cartao": None, "resumos": [], "cartoes": []})
