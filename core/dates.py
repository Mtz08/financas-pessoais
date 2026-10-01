"""Datas de calendário. Lançamentos usam date (sem hora), no fuso de São Paulo."""

import calendar
from collections.abc import Iterator
from datetime import date

from django.utils import timezone


def hoje() -> date:
    """Data de hoje em America/Sao_Paulo (não em UTC)."""
    return timezone.localdate()


def data_no_mes(ano: int, mes: int, dia: int) -> date:
    """Dia 31 em fevereiro vira 28 (ou 29): usa o último dia existente."""
    return date(ano, mes, min(dia, calendar.monthrange(ano, mes)[1]))


def primeiro_dia(d: date) -> date:
    return d.replace(day=1)


def ultimo_dia(d: date) -> date:
    return data_no_mes(d.year, d.month, 31)


def somar_meses(d: date, meses: int) -> date:
    """31/01 + 1 mês = 28/02 (ajusta para o último dia do mês)."""
    indice = d.year * 12 + (d.month - 1) + meses
    ano, mes = divmod(indice, 12)
    return data_no_mes(ano, mes + 1, d.day)


def meses_entre(inicio: date, fim: date) -> Iterator[date]:
    """Primeiros dias de cada mês de `inicio` até `fim`, inclusive."""
    atual, limite = primeiro_dia(inicio), primeiro_dia(fim)
    while atual <= limite:
        yield atual
        atual = somar_meses(atual, 1)


def parse_mes(texto: str | None, padrao: date) -> date:
    """"2026-09" -> date(2026, 9, 1). Valor inválido retorna `padrao`."""
    try:
        ano, mes = (int(p) for p in (texto or "").split("-"))
        return date(ano, mes, 1)
    except (ValueError, TypeError):
        return primeiro_dia(padrao)
