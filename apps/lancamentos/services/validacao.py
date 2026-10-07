from apps.categorias.models import Categoria
from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento
from core.exceptions import RegraDeNegocio

from .dados import DadosLancamento


def validar_conta_ativa(conta: Conta) -> None:
    if not conta.ativo:
        raise RegraDeNegocio(f"A conta “{conta}” está arquivada.")


def validar_categoria(categoria: Categoria, tipo: str) -> None:
    if not categoria.ativo:
        raise RegraDeNegocio(f"A categoria “{categoria}” está arquivada.")
    if categoria.tipo != tipo:
        raise RegraDeNegocio(f"A categoria “{categoria}” não é de {tipo.lower()}.")


def validar_mesmo_dono(*registros) -> None:
    """Conta e categoria (ou origem e destino) têm de ser do mesmo usuário."""
    if len({r.dono_id for r in registros if r is not None}) > 1:
        raise RegraDeNegocio("Os registros informados pertencem a usuários diferentes.")


def validar_valor(valor_centavos: int) -> None:
    if valor_centavos <= 0:
        raise RegraDeNegocio("O valor deve ser maior que zero.")


def validar_dados(dados: DadosLancamento, anterior: Lancamento | None = None) -> None:
    """Na edição, só exige conta/categoria ativa se ela foi trocada."""
    if dados.tipo not in (Lancamento.Tipo.RECEITA, Lancamento.Tipo.DESPESA):
        raise RegraDeNegocio("Tipo de lançamento inválido.")
    validar_valor(dados.valor_centavos)
    if not dados.descricao.strip():
        raise RegraDeNegocio("Informe a descrição.")
    validar_mesmo_dono(dados.conta, dados.categoria)
    if anterior is None or anterior.conta_id != dados.conta.pk:
        validar_conta_ativa(dados.conta)
    if anterior is None or anterior.categoria_id != dados.categoria.pk:
        validar_categoria(dados.categoria, dados.tipo)
    elif dados.categoria.tipo != dados.tipo:
        raise RegraDeNegocio("A categoria não corresponde ao tipo do lançamento.")
