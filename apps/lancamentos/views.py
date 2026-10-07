from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.relatorios.services import FiltroRelatorio, filtrar, totais
from core import dates
from core.views import processar_formulario

from .forms import ExcluirForm, FiltroForm, LancamentoForm, ParceladoForm, RecorrenciaForm, TransferenciaForm
from .models import Lancamento, Recorrencia
from .services import operacoes
from .services.dados import Escopo
from .services.lancamentos import alternar_status as alternar_status_servico
from .services.lancamentos import criar_lancamento
from .services.parcelamentos import criar_parcelamento
from .services.recorrencias import criar_recorrencia, encerrar_recorrencia, gerar_todas
from .services.transferencias import atualizar_transferencia, criar_transferencia, par_da_transferencia

def _lancamentos(request):
    """Lançamentos do usuário logado: toda busca por ID parte daqui (ID de outro dono = 404)."""
    return Lancamento.objects.do_usuario(request.user)


TIPOS_SIMPLES = {"receita": Lancamento.Tipo.RECEITA, "despesa": Lancamento.Tipo.DESPESA}


def lista(request):
    gerar_todas()  # materializa recorrências do mês (idempotente)
    filtro_form = FiltroForm(request.GET or None, usuario=request.user)
    filtro_form.is_valid()
    campos = getattr(filtro_form, "cleaned_data", {})
    mes = dates.parse_mes(campos.get("mes"), dates.hoje())
    consulta = filtrar(FiltroRelatorio(request.user, mes, dates.ultimo_dia(mes), campos.get("conta"), campos.get("categoria"),
                                       campos.get("tipo") or None))
    if campos.get("status"):
        consulta = consulta.filter(status=campos["status"])
    pagina = Paginator(consulta.order_by("-data", "-id"), 50).get_page(request.GET.get("pagina"))
    return render(request, "lancamentos/lista.html", {
        "filtro": filtro_form, "pagina": pagina, "totais": totais(consulta), "mes": mes,
        "mes_anterior": dates.somar_meses(mes, -1), "mes_seguinte": dates.somar_meses(mes, 1),
        "parametros": _parametros_sem(request, "pagina", "mes"),
    })


def _parametros_sem(request, *chaves) -> str:
    copia = request.GET.copy()
    for chave in chaves:
        copia.pop(chave, None)
    return copia.urlencode()


def novo(request, tipo):
    tipo_lancamento = TIPOS_SIMPLES.get(tipo) or _404()
    form = LancamentoForm(request.POST or None, usuario=request.user, tipo=tipo_lancamento)
    return processar_formulario(
        request, form, lambda f: criar_lancamento(f.para_dados()), sucesso="lancamentos:lista",
        template="lancamentos/form.html", contexto={"titulo": f"Nova {tipo}"}, mensagem="Lançamento criado.",
    )


def editar(request, pk):
    lancamento = get_object_or_404(_lancamentos(request).select_related("parcelamento", "recorrencia"), pk=pk)
    if lancamento.eh_transferencia:
        return redirect("lancamentos:transferencia_editar", pk=pk)
    form = LancamentoForm(request.POST or None, usuario=request.user, tipo=lancamento.tipo, lancamento=lancamento)
    return processar_formulario(
        request, form, lambda f: operacoes.editar(lancamento, f.para_dados(), f.escopo_escolhido()),
        sucesso="lancamentos:lista", template="lancamentos/form.html",
        contexto={"titulo": f"Editar {lancamento.descricao_completa}", "lancamento": lancamento},
    )


def excluir(request, pk):
    lancamento = get_object_or_404(_lancamentos(request).select_related("parcelamento", "recorrencia"), pk=pk)
    com_escopo = operacoes.aceita_escopo(lancamento)
    form = ExcluirForm(request.POST or None)
    if request.method == "POST" and (not com_escopo or form.is_valid()):
        escopo = Escopo(form.cleaned_data["escopo"]) if com_escopo else Escopo.ESTA
        with transaction.atomic():
            operacoes.excluir(lancamento, escopo)
        messages.success(request, "Lançamento excluído.")
        return redirect("lancamentos:lista")
    return render(request, "lancamentos/excluir.html", {"lancamento": lancamento, "form": form,
                                                         "com_escopo": com_escopo})


@require_POST
def alternar_status(request, pk):
    lancamento = get_object_or_404(_lancamentos(request), pk=pk)
    alternar_status_servico(lancamento)
    voltar = request.POST.get("voltar", "")
    # Só redireciona para o próprio site (evita open redirect).
    if url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()}):
        return redirect(voltar)
    return redirect("lancamentos:lista")


def transferencia_nova(request):
    form = TransferenciaForm(request.POST or None, usuario=request.user)
    return processar_formulario(
        request, form, lambda f: criar_transferencia(f.para_dados()), sucesso="lancamentos:lista",
        template="lancamentos/form.html", contexto={"titulo": "Nova transferência"},
        mensagem="Transferência registrada.",
    )


def transferencia_editar(request, pk):
    lancamento = get_object_or_404(_lancamentos(request), pk=pk, transferencia_id__isnull=False)
    saida, entrada = par_da_transferencia(lancamento)
    form = TransferenciaForm(request.POST or None, usuario=request.user, saida=saida, entrada=entrada)
    return processar_formulario(
        request, form, lambda f: atualizar_transferencia(lancamento, f.para_dados()),
        sucesso="lancamentos:lista", template="lancamentos/form.html",
        contexto={"titulo": "Editar transferência", "lancamento": lancamento},
    )


def parcelado_novo(request):
    form = ParceladoForm(request.POST or None, usuario=request.user)
    return processar_formulario(
        request, form, lambda f: criar_parcelamento(f.para_dados()), sucesso="lancamentos:lista",
        template="lancamentos/form.html", contexto={"titulo": "Nova compra parcelada"},
        mensagem="Compra parcelada registrada.",
    )


def recorrencias(request):
    ativas = Recorrencia.objects.do_usuario(request.user).select_related("conta", "categoria", "categoria__pai")
    return render(request, "lancamentos/recorrencias.html", {"recorrencias": ativas, "hoje": dates.hoje()})


def recorrencia_nova(request):
    form = RecorrenciaForm(request.POST or None, usuario=request.user)
    return processar_formulario(
        request, form, lambda f: criar_recorrencia(f.para_dados()), sucesso="lancamentos:recorrencias",
        template="form.html", contexto={"titulo": "Nova recorrência"}, mensagem="Recorrência criada.",
    )


@require_POST
def recorrencia_encerrar(request, pk):
    """Encerra hoje: mantém o histórico e apaga as ocorrências futuras pendentes."""
    recorrencia = get_object_or_404(Recorrencia.objects.do_usuario(request.user), pk=pk)
    encerrar_recorrencia(recorrencia, dates.hoje())
    messages.success(request, f"Recorrência “{recorrencia.descricao}” encerrada.")
    return redirect("lancamentos:recorrencias")


def _404():
    raise Http404
