"""Campos e formulários reutilizados por todos os apps."""

import uuid

from django import forms

from core.money import PADRAO_HTML, ValorInvalido, centavos_para_reais, reais_para_centavos


class CampoReais(forms.CharField):
    """Recebe "1.234,56" e entrega 123456 (centavos). Validação no navegador
    (pattern) e no servidor (to_python)."""

    TAMANHO_MAXIMO = 20

    def __init__(self, *args, permitir_negativo: bool = False, **kwargs):
        self.permitir_negativo = permitir_negativo
        # Sem max_length do CharField: o validador dele rodaria sobre o int já convertido.
        super().__init__(*args, **kwargs)
        self.widget.attrs.update(
            {"inputmode": "decimal", "placeholder": "0,00", "pattern": PADRAO_HTML, "autocomplete": "off",
             "title": "Use o formato 1.234,56", "maxlength": self.TAMANHO_MAXIMO}
        )

    def to_python(self, value):
        texto = super().to_python(value)
        if texto in self.empty_values:
            return None
        if len(texto) > self.TAMANHO_MAXIMO:
            raise forms.ValidationError("Valor longo demais.")
        try:
            return reais_para_centavos(texto, permitir_negativo=self.permitir_negativo)
        except ValorInvalido as erro:
            raise forms.ValidationError(str(erro)) from erro

    def prepare_value(self, value):
        return centavos_para_reais(value, simbolo=False) if isinstance(value, int) else value


class CampoData(forms.DateField):
    widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class FormIdempotente(forms.Form):
    """Inclui uma chave única por exibição do formulário (anti duplo envio)."""

    chave = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["chave"].initial = uuid.uuid4()


class ModelFormIdempotente(forms.ModelForm):
    chave = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["chave"].initial = uuid.uuid4()
