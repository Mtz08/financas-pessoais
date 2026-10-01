from urllib.parse import urlencode

from django import forms
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render

from apps.categorias.models import Categoria
from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento
from core import dates
from core.forms import CampoData

from .services import FiltroRelatorio, escrever_csv, filtrar, totais

LIMITE_EM_TELA = 1000


class RelatorioForm(forms.Form):
    inicio = CampoData(label="De")
    fim = CampoData(label="Até")
    conta = forms.ModelChoiceField(queryset=Conta.objects.all(), required=False, empty_label="Todas")
    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.select_related("pai").order_by("tipo", "pai__nome", "nome"),
        required=False, empty_label="Todas",
    )
    tipo = forms.ChoiceField(
        choices=[("", "Receitas e despesas"), ("RECEITA", "Receitas"), ("DESPESA", "Despesas")], required=False
    )

    def clean(self):
        dados = super().clean()
        if dados.get("inicio") and dados.get("fim") and dados["fim"] < dados["inicio"]:
            self.add_error("fim", "A data final deve ser posterior à inicial.")
        return dados

    def filtro(self) -> FiltroRelatorio:
        d = self.cleaned_data
        return FiltroRelatorio(d["inicio"], d["fim"], d.get("conta"), d.get("categoria"), d.get("tipo") or None)


def index(request):
    hoje = dates.hoje()
    iniciais = {"inicio": dates.primeiro_dia(hoje), "fim": dates.ultimo_dia(hoje)}
    form = RelatorioForm(request.GET or iniciais)
    if not form.is_valid():
        return render(request, "relatorios/index.html", {"form": form})
    consulta = filtrar(form.filtro())
    if not form.cleaned_data.get("tipo"):  # sem filtro de tipo, esconde transferências
        consulta = consulta.exclude(tipo__in=Lancamento.TIPOS_TRANSFERENCIA)
    if request.GET.get("formato") == "csv":
        return _csv(consulta, form.filtro())
    return render(request, "relatorios/index.html", {
        "form": form,
        "totais": totais(consulta),
        "por_categoria": _por_categoria(consulta),
        "lancamentos": consulta[:LIMITE_EM_TELA],
        "truncado": consulta.count() > LIMITE_EM_TELA,
        "query_csv": _query_do_filtro(form.cleaned_data),
    })


def _query_do_filtro(dados: dict) -> str:
    return urlencode({
        "inicio": dados["inicio"].isoformat(),
        "fim": dados["fim"].isoformat(),
        "conta": getattr(dados.get("conta"), "pk", ""),
        "categoria": getattr(dados.get("categoria"), "pk", ""),
        "tipo": dados.get("tipo") or "",
    })


def _por_categoria(consulta):
    return (
        consulta.values("tipo", "categoria__pai__nome", "categoria__nome")
        .annotate(total=Sum("valor_centavos"))
        .order_by("tipo", "-total")
    )


def _csv(consulta, filtro: FiltroRelatorio) -> HttpResponse:
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    nome = f"lancamentos_{filtro.inicio:%Y%m%d}_{filtro.fim:%Y%m%d}.csv"
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    resposta.write("﻿")  # BOM: o Excel reconhece UTF-8 e acentos
    escrever_csv(consulta, resposta)
    return resposta
