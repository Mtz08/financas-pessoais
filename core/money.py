"""Dinheiro sempre em centavos inteiros (int). Nunca float."""

import re

# "1234", "1234,5", "1.234,56" — ponto só como separador de milhar.
_FORMATO_BR = re.compile(r"^(\d{1,3}(\.\d{3})+|\d+)(,\d{1,2})?$")
PADRAO_HTML = r"-?(\d{1,3}(\.\d{3})+|\d+)(,\d{1,2})?"


class ValorInvalido(ValueError):
    pass


def reais_para_centavos(texto: str, permitir_negativo: bool = False) -> int:
    """Converte "1.234,56" em 123456. Rejeita formatos ambíguos como "10.5"."""
    limpo = (texto or "").replace("R$", "").replace("\xa0", "").replace(" ", "")
    negativo = limpo.startswith("-")
    if negativo:
        if not permitir_negativo:
            raise ValorInvalido("Informe um valor positivo.")
        limpo = limpo[1:]
    if not _FORMATO_BR.match(limpo):
        raise ValorInvalido("Valor inválido. Use o formato 1.234,56.")
    inteiro, _, fracao = limpo.partition(",")
    centavos = int(inteiro.replace(".", "")) * 100 + int(fracao.ljust(2, "0"))
    return -centavos if negativo else centavos


def centavos_para_reais(centavos: int, simbolo: bool = True) -> str:
    """123456 -> "R$ 1.234,56"; -500 -> "-R$ 5,00"."""
    sinal = "-" if centavos < 0 else ""
    inteiro, fracao = divmod(abs(centavos), 100)
    milhar = f"{inteiro:,}".replace(",", ".")
    prefixo = "R$ " if simbolo else ""
    return f"{sinal}{prefixo}{milhar},{fracao:02d}"


def dividir_em_parcelas(total_centavos: int, quantidade: int) -> list[int]:
    """Divide em parcelas iguais; a diferença de centavos vai para a última.

    Ex.: 10000 em 3 -> [3333, 3333, 3334].
    """
    if quantidade < 1:
        raise ValorInvalido("A quantidade de parcelas deve ser ao menos 1.")
    if total_centavos < quantidade:
        raise ValorInvalido("Valor insuficiente para essa quantidade de parcelas.")
    base = total_centavos // quantidade
    return [base] * (quantidade - 1) + [total_centavos - base * (quantidade - 1)]
