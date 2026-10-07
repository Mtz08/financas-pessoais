from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core import dates
from core.forms import CampoData, CampoReais, ModelFormIdempotente
from core.views import processar_formulario

from .models import Divida
from .services import dar_baixa, reabrir, resumir


class DividaForm(ModelFormIdempotente):
    valor_centavos = CampoReais(label="Valor (R$)")
    data = CampoData(label="Desde")
    vencimento = CampoData(label="Vencimento (opcional)", required=False)

    class Meta:
        model = Divida
        fields = ["credor", "descricao", "valor_centavos", "data", "vencimento", "observacao"]
        widgets = {"observacao": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data"].initial = dates.hoje()
        self.fields["credor"].widget.attrs["list"] = "credores"  # sugere credores já usados

    def clean_credor(self):
        return self.cleaned_data["credor"].strip()


def lista(request):
    hoje = dates.hoje()
    return render(request, "dividas/lista.html", {
        "abertas": Divida.objects.filter(paga=False),
        "pagas": Divida.objects.filter(paga=True).order_by("-data_pagamento", "-id")[:50],
        "resumo": resumir(hoje),
        "hoje": hoje,
    })


def _contexto_form(titulo: str) -> dict:
    credores = Divida.objects.values_list("credor", flat=True).distinct().order_by("credor")
    return {"titulo": titulo, "credores": credores}


def nova(request):
    form = DividaForm(request.POST or None)
    return processar_formulario(request, form, lambda f: f.save(), sucesso="dividas:lista",
                                template="dividas/form.html", contexto=_contexto_form("Nova dívida"),
                                mensagem="Dívida registrada.")


def editar(request, pk):
    divida = get_object_or_404(Divida, pk=pk)
    form = DividaForm(request.POST or None, instance=divida)
    return processar_formulario(request, form, lambda f: f.save(), sucesso="dividas:lista",
                                template="dividas/form.html",
                                contexto={**_contexto_form("Editar dívida"), "divida": divida})


@require_POST
def baixa(request, pk):
    divida = dar_baixa(get_object_or_404(Divida, pk=pk, paga=False))
    messages.success(request, f"Baixa registrada: “{divida}”.")
    return redirect("dividas:lista")


@require_POST
def reabrir_divida(request, pk):
    divida = reabrir(get_object_or_404(Divida, pk=pk, paga=True))
    messages.success(request, f"Dívida reaberta: “{divida}”.")
    return redirect("dividas:lista")


@require_POST
def excluir(request, pk):
    divida = get_object_or_404(Divida, pk=pk)
    divida.delete()
    messages.success(request, f"Dívida excluída: “{divida}”.")
    return redirect("dividas:lista")
