from django import forms

from core.forms import CampoData, CampoReais, ModelFormIdempotente

from .models import Conta


class ContaForm(ModelFormIdempotente):
    saldo_inicial_centavos = CampoReais(label="Saldo inicial (R$)", permitir_negativo=True, initial=0)
    data_saldo_inicial = CampoData(label="Data do saldo inicial")
    limite_centavos = CampoReais(label="Limite (R$)", required=False)

    class Meta:
        model = Conta
        fields = ["nome", "tipo", "saldo_inicial_centavos", "data_saldo_inicial",
                  "dia_fechamento", "dia_vencimento", "limite_centavos"]
        labels = {"dia_fechamento": "Dia de fechamento", "dia_vencimento": "Dia de vencimento"}
        widgets = {
            "dia_fechamento": forms.NumberInput(attrs={"min": 1, "max": 31, "data-so-cartao": ""}),
            "dia_vencimento": forms.NumberInput(attrs={"min": 1, "max": 31, "data-so-cartao": ""}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["limite_centavos"].widget.attrs["data-so-cartao"] = ""

    def clean(self):
        dados = super().clean()
        tipo = dados.get("tipo")
        if self._trocou_tipo_com_lancamentos(tipo):
            raise forms.ValidationError("Não é possível mudar o tipo de uma conta que já tem lançamentos.")
        if tipo == Conta.Tipo.CARTAO:
            for campo in ("dia_fechamento", "dia_vencimento"):
                if not dados.get(campo):
                    self.add_error(campo, "Obrigatório para cartão de crédito.")
        else:
            dados["dia_fechamento"] = dados["dia_vencimento"] = dados["limite_centavos"] = None
        return dados

    def _trocou_tipo_com_lancamentos(self, tipo) -> bool:
        conta = self.instance
        return bool(conta.pk and tipo != conta.tipo and conta.lancamentos.exists())
