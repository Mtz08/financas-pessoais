from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.lancamentos.forms import categorias_do_tipo
from core import dates
from core.forms import CampoReais, ModelFormIdempotente
from core.views import processar_formulario

from .models import Orcamento
from .services import situacao_do_mes


class OrcamentoForm(ModelFormIdempotente):
    vigente_desde = forms.DateField(label="Vale a partir de", input_formats=["%Y-%m"],
                                    widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"))
    limite_centavos = CampoReais(label="Limite mensal (R$)")

    class Meta:
        model = Orcamento
        fields = ["categoria", "vigente_desde", "limite_centavos"]

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = categorias_do_tipo(usuario, "DESPESA")
        self.fields["vigente_desde"].initial = dates.primeiro_dia(dates.hoje())


def lista(request):
    mes = dates.parse_mes(request.GET.get("mes"), dates.hoje())
    form = OrcamentoForm(request.POST or None, usuario=request.user)
    contexto = {
        "mes": mes,
        "situacoes": situacao_do_mes(request.user, mes),
        "orcamentos": Orcamento.objects.do_usuario(request.user).select_related("categoria", "categoria__pai"),
        "mes_anterior": dates.somar_meses(mes, -1),
        "mes_seguinte": dates.somar_meses(mes, 1),
    }
    return processar_formulario(request, form, lambda f: f.save(), sucesso="orcamentos:lista",
                                template="orcamentos/lista.html", contexto=contexto, mensagem="Orçamento salvo.")


@require_POST
def excluir(request, pk):
    orcamento = get_object_or_404(Orcamento.objects.do_usuario(request.user), pk=pk)
    orcamento.delete()
    messages.success(request, "Orçamento removido.")
    return redirect("orcamentos:lista")
