from django import template

from core.money import centavos_para_reais

register = template.Library()


@register.filter
def reais(centavos) -> str:
    """{{ 123456|reais }} -> "R$ 1.234,56"."""
    if centavos in (None, ""):
        return ""
    return centavos_para_reais(int(centavos))


@register.filter
def sinal(centavos) -> str:
    """Classe CSS conforme o sinal do valor."""
    return "negativo" if centavos and int(centavos) < 0 else "positivo"
