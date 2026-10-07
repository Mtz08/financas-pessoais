from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import dates
from core.forms import CampoData, CampoReais, ComDono, ModelFormIdempotente
from core.views import processar_formulario

from .models import Divida
from .services import agrupar_por_mes, dar_baixa, reabrir, resumir


class DividaForm(ComDono, ModelFormIdempotente):
    valor_centavos = CampoReais(label="Valor (R$)")
    data = CampoData(label="Data da dívida", help_text="Define em qual mês ela aparece na aba Por mês.")
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


VISOES = ("lista", "mes")


def lista(request):
    hoje = dates.hoje()
    visao = request.GET.get("visao") if request.GET.get("visao") in VISOES else "lista"
    dividas = Divida.objects.do_usuario(request.user)
    abertas = dividas.filter(paga=False)
    return render(request, "dividas/lista.html", {
        "visao": visao,
        "abertas": abertas,
        "grupos": agrupar_por_mes(abertas) if visao == "mes" else [],
        "pagas": dividas.filter(paga=True).order_by("-data_pagamento", "-id")[:50],
        "resumo": resumir(request.user, hoje),
        "hoje": hoje,
        "mes_atual": dates.primeiro_dia(hoje),
    })


def _contexto_form(request, titulo: str) -> dict:
    credores = Divida.objects.do_usuario(request.user).values_list("credor", flat=True).distinct().order_by("credor")
    return {"titulo": titulo, "credores": credores}


def nova(request):
    form = DividaForm(request.POST or None, usuario=request.user)
    return processar_formulario(request, form, lambda f: f.save(), sucesso="dividas:lista",
                                template="dividas/form.html", contexto=_contexto_form(request, "Nova dívida"),
                                mensagem="Dívida registrada.")


def editar(request, pk):
    divida = get_object_or_404(Divida.objects.do_usuario(request.user), pk=pk)
    form = DividaForm(request.POST or None, usuario=request.user, instance=divida)
    return processar_formulario(request, form, lambda f: f.save(), sucesso="dividas:lista",
                                template="dividas/form.html",
                                contexto={**_contexto_form(request, "Editar dívida"), "divida": divida})


def _voltar_para_lista(request):
    """Volta para a mesma aba (Lista ou Por mês) de onde a ação partiu."""
    if request.GET.get("visao") == "mes":
        return redirect(f"{reverse('dividas:lista')}?visao=mes")
    return redirect("dividas:lista")


@require_POST
def baixa(request, pk):
    divida = dar_baixa(get_object_or_404(Divida.objects.do_usuario(request.user), pk=pk, paga=False))
    messages.success(request, f"Baixa registrada: “{divida}”.")
    return _voltar_para_lista(request)


@require_POST
def reabrir_divida(request, pk):
    divida = reabrir(get_object_or_404(Divida.objects.do_usuario(request.user), pk=pk, paga=True))
    messages.success(request, f"Dívida reaberta: “{divida}”.")
    return redirect("dividas:lista")


@require_POST
def excluir(request, pk):
    divida = get_object_or_404(Divida.objects.do_usuario(request.user), pk=pk)
    divida.delete()
    messages.success(request, f"Dívida excluída: “{divida}”.")
    return redirect("dividas:lista")
