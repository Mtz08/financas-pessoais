from django import forms

from core.forms import ComDono, ModelFormIdempotente

from .models import Categoria


class CategoriaForm(ComDono, ModelFormIdempotente):
    class Meta:
        model = Categoria
        fields = ["nome", "tipo", "pai"]
        labels = {"pai": "Categoria pai (deixe vazio para criar uma principal)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pais = Categoria.objects.do_usuario(self.usuario).filter(pai__isnull=True, ativo=True)
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
        nome, tipo = (dados.get("nome") or "").strip(), dados.get("tipo")
        if nome and tipo and not pai and self._outros_do_usuario(Categoria).filter(
                pai__isnull=True, tipo=tipo, nome__iexact=nome).exists():
            self.add_error("nome", "Você já tem uma categoria principal com esse nome.")
        return dados
