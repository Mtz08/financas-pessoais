"""Formulários de lançamentos. Todos recebem `usuario` e só oferecem contas e
categorias desse usuário: um ID de outro dono enviado à força é recusado pelo
próprio ModelChoiceField ("escolha inválida")."""

from django import forms
from django.db.models import Q

from apps.categorias.models import Categoria
from apps.contas.models import Conta
from core import dates
from core.forms import CampoData, CampoReais, FormIdempotente

from .models import Lancamento
from .services.dados import ESCOPO_ROTULOS, DadosLancamento, DadosParcelamento, DadosTransferencia, Escopo
from .services.recorrencias import DadosRecorrencia

ESCOPOS = [(escopo.value, rotulo) for escopo, rotulo in ESCOPO_ROTULOS.items()]


def contas_ativas(usuario, incluir: Conta | None = None, sem_cartao: bool = False):
    consulta = Conta.objects.do_usuario(usuario).filter(Q(ativo=True) | Q(pk=getattr(incluir, "pk", None)))
    return consulta.exclude(tipo=Conta.Tipo.CARTAO) if sem_cartao else consulta


def categorias_do_tipo(usuario, tipo: str, incluir: Categoria | None = None):
    return (
        Categoria.objects.do_usuario(usuario)
        .filter(Q(ativo=True) | Q(pk=getattr(incluir, "pk", None)), tipo=tipo)
        .select_related("pai")
        .order_by("pai__nome", "nome")
    )


class LancamentoForm(FormIdempotente):
    conta = forms.ModelChoiceField(queryset=Conta.objects.none())
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.none())
    descricao = forms.CharField(label="Descrição", max_length=120)
    valor = CampoReais(label="Valor (R$)")
    data = CampoData(initial=dates.hoje)
    status = forms.ChoiceField(choices=Lancamento.Status.choices, initial=Lancamento.Status.PENDENTE)
    escopo = forms.ChoiceField(
        label="Aplicar a", choices=ESCOPOS, initial=Escopo.ESTA, widget=forms.RadioSelect, required=False
    )

    def __init__(self, *args, usuario, tipo: str, lancamento: Lancamento | None = None, **kwargs):
        if lancamento:
            kwargs.setdefault("initial", _iniciais(lancamento))
        super().__init__(*args, **kwargs)
        self.tipo = tipo
        self.fields["conta"].queryset = contas_ativas(usuario, getattr(lancamento, "conta", None))
        self.fields["categoria"].queryset = categorias_do_tipo(usuario, tipo, getattr(lancamento, "categoria", None))
        self.fields["data"].initial = dates.hoje()
        if not (lancamento and (lancamento.parcelamento_id or lancamento.recorrencia_id)):
            del self.fields["escopo"]

    def para_dados(self) -> DadosLancamento:
        d = self.cleaned_data
        return DadosLancamento(self.tipo, d["conta"], d["categoria"], d["descricao"], d["valor"], d["data"],
                               d["status"])

    def escopo_escolhido(self) -> Escopo:
        return Escopo(self.cleaned_data.get("escopo") or Escopo.ESTA)


def _iniciais(lancamento: Lancamento) -> dict:
    return {
        "conta": lancamento.conta,
        "categoria": lancamento.categoria,
        "descricao": lancamento.descricao,
        "valor": lancamento.valor_centavos,
        "data": lancamento.data,
        "status": lancamento.status,
    }


class TransferenciaForm(FormIdempotente):
    origem = forms.ModelChoiceField(queryset=Conta.objects.none(), label="De")
    destino = forms.ModelChoiceField(queryset=Conta.objects.none(), label="Para")
    valor = CampoReais(label="Valor (R$)")
    data = CampoData()
    descricao = forms.CharField(label="Descrição", max_length=120, initial="Transferência")
    status = forms.ChoiceField(choices=Lancamento.Status.choices, initial=Lancamento.Status.PAGO)

    def __init__(self, *args, usuario, saida: Lancamento | None = None, entrada: Lancamento | None = None,
                 **kwargs):
        if saida and entrada:
            kwargs.setdefault("initial", {"origem": saida.conta, "destino": entrada.conta, "valor": saida.valor_centavos,
                                          "data": saida.data, "descricao": saida.descricao, "status": saida.status})
        super().__init__(*args, **kwargs)
        self.fields["origem"].queryset = contas_ativas(usuario, getattr(saida, "conta", None))
        self.fields["destino"].queryset = contas_ativas(usuario, getattr(entrada, "conta", None))
        self.fields["data"].initial = dates.hoje()

    def clean(self):
        dados = super().clean()
        if dados.get("origem") and dados.get("origem") == dados.get("destino"):
            self.add_error("destino", "Escolha uma conta diferente da origem.")
        return dados

    def para_dados(self) -> DadosTransferencia:
        d = self.cleaned_data
        return DadosTransferencia(d["origem"], d["destino"], d["valor"], d["data"], d["descricao"], d["status"])


class ParceladoForm(FormIdempotente):
    conta = forms.ModelChoiceField(queryset=Conta.objects.none())
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.none())
    descricao = forms.CharField(label="Descrição", max_length=120)
    valor_total = CampoReais(label="Valor total (R$)")
    quantidade_parcelas = forms.IntegerField(label="Parcelas", min_value=2, max_value=72, initial=2)
    data_compra = CampoData(label="Data da compra")

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["conta"].queryset = contas_ativas(usuario)
        self.fields["categoria"].queryset = categorias_do_tipo(usuario, Lancamento.Tipo.DESPESA)
        self.fields["data_compra"].initial = dates.hoje()

    def clean(self):
        dados = super().clean()
        total, qtd = dados.get("valor_total"), dados.get("quantidade_parcelas")
        if total and qtd and total < qtd:
            self.add_error("valor_total", "Valor pequeno demais para essa quantidade de parcelas.")
        return dados

    def para_dados(self) -> DadosParcelamento:
        d = self.cleaned_data
        return DadosParcelamento(d["conta"], d["categoria"], d["descricao"], d["valor_total"],
                                 d["quantidade_parcelas"], d["data_compra"])


class ExcluirForm(forms.Form):
    escopo = forms.ChoiceField(label="Excluir", choices=ESCOPOS, initial=Escopo.ESTA, widget=forms.RadioSelect)


class RecorrenciaForm(FormIdempotente):
    tipo = forms.ChoiceField(choices=[("DESPESA", "Despesa"), ("RECEITA", "Receita")])
    conta = forms.ModelChoiceField(queryset=Conta.objects.none())
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.none())
    descricao = forms.CharField(label="Descrição", max_length=120)
    valor = CampoReais(label="Valor (R$)")
    dia = forms.IntegerField(label="Dia do mês", min_value=1, max_value=31,
                             help_text="Nos meses mais curtos, usa o último dia (ex.: 31 → 28/02).")
    data_inicio = CampoData(label="Início")
    data_fim = CampoData(label="Fim (opcional)", required=False)

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["conta"].queryset = contas_ativas(usuario)
        self.fields["categoria"].queryset = (
            Categoria.objects.do_usuario(usuario).filter(ativo=True).select_related("pai")
            .order_by("tipo", "pai__nome", "nome")
        )
        self.fields["data_inicio"].initial = dates.hoje()

    def clean(self):
        dados = super().clean()
        categoria, tipo = dados.get("categoria"), dados.get("tipo")
        if categoria and tipo and categoria.tipo != tipo:
            self.add_error("categoria", "A categoria não corresponde ao tipo escolhido.")
        inicio, fim = dados.get("data_inicio"), dados.get("data_fim")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "O fim deve ser depois do início.")
        return dados

    def para_dados(self) -> DadosRecorrencia:
        d = self.cleaned_data
        return DadosRecorrencia(d["tipo"], d["conta"], d["categoria"], d["descricao"], d["valor"], d["dia"],
                                d["data_inicio"], d["data_fim"])


class FiltroForm(forms.Form):
    """Filtros da listagem (GET). Valores inválidos são simplesmente ignorados."""

    mes = forms.CharField(required=False, widget=forms.TextInput(attrs={"type": "month"}))
    conta = forms.ModelChoiceField(queryset=Conta.objects.none(), required=False, empty_label="Todas as contas")
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.none(), required=False,
                                       empty_label="Todas as categorias")
    tipo = forms.ChoiceField(choices=[("", "Todos os tipos"), *Lancamento.Tipo.choices], required=False)
    status = forms.ChoiceField(choices=[("", "Qualquer status"), *Lancamento.Status.choices], required=False)

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["conta"].queryset = Conta.objects.do_usuario(usuario)
        self.fields["categoria"].queryset = (
            Categoria.objects.do_usuario(usuario).select_related("pai").order_by("tipo", "pai__nome", "nome")
        )
