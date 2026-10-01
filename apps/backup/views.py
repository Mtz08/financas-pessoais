import json

from django import forms
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.exceptions import RegraDeNegocio

from .services import exportar, importar

TAMANHO_MAXIMO = 20 * 1024 * 1024  # 20 MB


class ImportarForm(forms.Form):
    arquivo = forms.FileField(label="Arquivo de backup (.json)",
                              widget=forms.ClearableFileInput(attrs={"accept": "application/json,.json"}))
    confirmar = forms.BooleanField(label="Entendo que TODOS os dados atuais serão substituídos.")

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        if arquivo.size > TAMANHO_MAXIMO:
            raise forms.ValidationError("Arquivo maior que 20 MB.")
        return arquivo


def index(request):
    return render(request, "backup/index.html", {"form": ImportarForm()})


def baixar(request):
    agora = timezone.localtime()
    resposta = HttpResponse(json.dumps(exportar(), ensure_ascii=False, indent=1),
                            content_type="application/json; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="financas_backup_{agora:%Y%m%d_%H%M}.json"'
    return resposta


@require_POST
def restaurar(request):
    form = ImportarForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, "backup/index.html", {"form": form})
    try:
        contagem = importar(form.cleaned_data["arquivo"].read())
    except RegraDeNegocio as erro:
        form.add_error("arquivo", str(erro))
        return render(request, "backup/index.html", {"form": form})
    resumo = ", ".join(f"{qtd} {nome}" for nome, qtd in contagem.items())
    messages.success(request, f"Backup restaurado: {resumo}.")
    return redirect("dashboard")
