from django import forms

from core.forms import ModelFormIdempotente

from .models import Categoria


class CategoriaForm(ModelFormIdempotente):
    class Meta:
        model = Categoria
        fields = ["nome", "tipo", "pai"]
        labels = {"pai": "Categoria pai (deixe vazio para criar uma principal)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pais = Categoria.objects.filter(pai__isnull=True, ativo=True)
        if self.instance.pk:
            pais = pais.exclude(pk=self.instance.pk)
        self.fields["pai"].queryset = pais

    def clean(self):
        dados = super().clean()
        pai = dados.get("pai")
        if pai and self.instance.pk and self.instance.subcategorias.exists():
            raise forms.ValidationError("Esta categoria tem subcategorias; ela não pode virar subcategoria.")
        if pai and dados.get("tipo") and pai.tipo != dados["tipo"]:
            self.add_error("pai", "A categoria pai deve ser do mesmo tipo.")
        return dados
