from datetime import date

import pytest

from core import dates
from core.money import ValorInvalido, centavos_para_reais, dividir_em_parcelas, reais_para_centavos


@pytest.mark.parametrize(
    ("texto", "centavos"),
    [("1.234,56", 123456), ("1234,56", 123456), ("10", 1000), ("0,5", 50), ("0,05", 5),
     ("R$ 1.000.000,00", 100_000_000), ("  25,90 ", 2590)],
)
def test_converte_reais_para_centavos(texto, centavos):
    assert reais_para_centavos(texto) == centavos


@pytest.mark.parametrize("texto", ["10.5", "1,234", "abc", "", "1.23,00", "12,345", "1e3"])
def test_rejeita_formatos_ambiguos_ou_invalidos(texto):
    with pytest.raises(ValorInvalido):
        reais_para_centavos(texto)


def test_negativo_so_quando_permitido():
    assert reais_para_centavos("-50,00", permitir_negativo=True) == -5000
    with pytest.raises(ValorInvalido):
        reais_para_centavos("-50,00")


@pytest.mark.parametrize(
    ("centavos", "texto"),
    [(123456, "R$ 1.234,56"), (5, "R$ 0,05"), (-500, "-R$ 5,00"), (0, "R$ 0,00"), (100_000_000, "R$ 1.000.000,00")],
)
def test_formata_em_reais(centavos, texto):
    assert centavos_para_reais(centavos) == texto


def test_diferenca_de_centavos_vai_para_ultima_parcela():
    assert dividir_em_parcelas(10_000, 3) == [3333, 3333, 3334]


@pytest.mark.parametrize("total", [1_000, 9_999, 359_990, 7, 100_001])
@pytest.mark.parametrize("quantidade", [2, 3, 7, 12])
def test_soma_das_parcelas_e_sempre_o_total(total, quantidade):
    if total < quantidade:
        pytest.skip("valor menor que a quantidade é recusado em outro teste")
    parcelas = dividir_em_parcelas(total, quantidade)
    assert sum(parcelas) == total
    assert len(parcelas) == quantidade
    assert max(parcelas) - min(parcelas) < quantidade  # diferença só de centavos


def test_parcelamento_sem_centavo_suficiente_e_recusado():
    with pytest.raises(ValorInvalido):
        dividir_em_parcelas(2, 3)


@pytest.mark.parametrize(
    ("ano", "mes", "dia", "esperado"),
    [(2026, 2, 31, date(2026, 2, 28)), (2028, 2, 31, date(2028, 2, 29)), (2026, 4, 31, date(2026, 4, 30)),
     (2026, 1, 31, date(2026, 1, 31))],
)
def test_dia_31_usa_ultimo_dia_do_mes(ano, mes, dia, esperado):
    assert dates.data_no_mes(ano, mes, dia) == esperado


def test_somar_meses_ajusta_fim_de_mes_e_vira_o_ano():
    assert dates.somar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert dates.somar_meses(date(2026, 12, 15), 2) == date(2027, 2, 15)
    assert dates.somar_meses(date(2026, 3, 10), -3) == date(2025, 12, 10)


def test_meses_entre_inclui_as_pontas():
    assert list(dates.meses_entre(date(2026, 11, 20), date(2027, 1, 5))) == [
        date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 1)]


def test_parse_mes_invalido_volta_para_o_padrao():
    assert dates.parse_mes("2026-13", date(2026, 5, 20)) == date(2026, 5, 1)
    assert dates.parse_mes("2026-07", date(2026, 5, 20)) == date(2026, 7, 1)
