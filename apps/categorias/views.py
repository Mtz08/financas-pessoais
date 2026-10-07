from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.views import excluir_ou_avisar, processar_formulario

from .forms import CategoriaForm
from .models import Categoria


def lista(request):
    raizes = Categoria.objects.do_usuario(request.user).filter(pai__isnull=True).prefetch_related("subcategorias").order_by("tipo", "nome")
    return render(request, "categorias/lista.html", {"raizes": raizes})


def nova(request):
    form = CategoriaForm(request.POST or None, usuario=request.user, initial={"pai": request.GET.get("pai"), "tipo": request.GET.get("tipo")})
    return processar_formulario(request, form, lambda f: f.save(), sucesso="categorias:lista",
                                template="form.html", contexto={"titulo": "Nova categoria"},
                                mensagem="Categoria criada.")


def editar(request, pk):
    categoria = get_object_or_404(Categoria.objects.do_usuario(request.user), pk=pk)
    form = CategoriaForm(request.POST or None, usuario=request.user, instance=categoria)
    return processar_formulario(request, form, lambda f: f.save(), sucesso="categorias:lista",
                                template="form.html", contexto={"titulo": f"Editar {categoria}"})


@require_POST
def arquivar(request, pk):
    """Arquivar a categoria-pai arquiva também as subcategorias."""
    categoria = get_object_or_404(Categoria.objects.do_usuario(request.user), pk=pk)
    categoria.ativo = not categoria.ativo
    categoria.save(update_fields=["ativo", "atualizado_em"])
    if not categoria.ativo:
        categoria.subcategorias.update(ativo=False)
    messages.success(request, f"Categoria “{categoria}” {'reativada' if categoria.ativo else 'arquivada'}.")
    return redirect("categorias:lista")


@require_POST
def excluir(request, pk):
    return excluir_ou_avisar(request, get_object_or_404(Categoria.objects.do_usuario(request.user), pk=pk), "categorias:lista")
