from django import template
from django.utils.safestring import mark_safe

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


# Ícones de traço (24x24) no estilo Lucide. Conteúdo fixo, sem dado do usuário.
_ICONES = {
    "inicio": '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/>'
              '<rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    "lancamentos": '<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>',
    "cartao": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
    "recorrencia": '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/>'
                   '<path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
    "orcamento": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "relatorio": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "conta": '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2'
             'a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    "categoria": '<path d="M12.6 2.6A2 2 0 0 0 11.2 2H4a2 2 0 0 0-2 2v7.2a2 2 0 0 0 .6 1.4l8.7 8.7a2.4 2.4 0 0 0 3.4 0'
                 'l6.6-6.6a2.4 2.4 0 0 0 0-3.4z"/><circle cx="7.5" cy="7.5" r="1"/>',
    "backup": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/>'
              '<path d="M3 12a9 3 0 0 0 18 0"/>',
    "sair": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    "mais": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "entrada": '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    "saida": '<path d="m22 17-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>',
    "saldo": '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2"/>'
             '<path d="M6 12h.01M18 12h.01"/>',
    "resultado": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "calendario": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "alerta": '<path d="m21.7 18-8-14a2 2 0 0 0-3.5 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3"/>'
              '<path d="M12 9v4"/><path d="M12 17h.01"/>',
    "transferir": '<path d="M7 17 17 7"/><path d="M7 7h10v10"/>',
    "parcelado": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>',
    "divida": '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/>'
              '<path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
    "pessoas": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
               '<path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "anterior": '<path d="m15 18-6-6 6-6"/>',
    "proximo": '<path d="m9 18 6-6-6-6"/>',
}


@register.simple_tag
def icone(nome: str, classe: str = "icone") -> str:
    return mark_safe(
        f'<svg class="{classe}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_ICONES[nome]}</svg>'
    )
