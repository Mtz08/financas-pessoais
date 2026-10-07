import json
import uuid
from datetime import date

import pytest
from django.db import IntegrityError

from apps.backup.services import exportar, importar
from apps.dividas.models import Divida
from apps.dividas.services import dar_baixa, reabrir, resumir
from apps.lancamentos.models import Lancamento
from apps.lancamentos.services.saldos import saldo_conta


@pytest.fixture
def divida(db):
    def fabricar(**campos) -> Divida:
        padrao = {"credor": "Credor Fictício", "descricao": "Empréstimo", "valor_centavos": 50_000,
                  "data": date(2026, 9, 1)}
        return Divida.objects.create(**{**padrao, **campos})
    return fabricar


def _post_nova(cliente, chave, **campos):
    dados = {"chave": str(chave), "credor": "  Credor Fictício  ", "descricao": "Conserto",
             "valor_centavos": "1.500,00", "data": "2026-10-01", "vencimento": "", "observacao": "", **campos}
    return cliente.post("/dividas/nova/", dados)


def test_cadastra_divida_pela_tela(cliente_logado, db):
    resposta = _post_nova(cliente_logado, uuid.uuid4())
    assert resposta.status_code == 302
    d = Divida.objects.get()
    assert (d.credor, d.valor_centavos, d.paga, d.vencimento) == ("Credor Fictício", 150_000, False, None)


def test_envio_duplicado_cadastra_uma_vez(cliente_logado, db):
    chave = uuid.uuid4()
    _post_nova(cliente_logado, chave)
    _post_nova(cliente_logado, chave)
    assert Divida.objects.count() == 1


@pytest.mark.parametrize("valor", ["0,00", "-10,00", "abc"])
def test_valor_invalido_e_recusado(cliente_logado, db, valor):
    resposta = _post_nova(cliente_logado, uuid.uuid4(), valor_centavos=valor)
    assert resposta.status_code == 200
    assert not Divida.objects.exists()


def test_divida_nao_mexe_em_saldo_nem_lancamentos(cliente_logado, corrente):
    antes = saldo_conta(corrente, ate=date(2026, 12, 31))
    _post_nova(cliente_logado, uuid.uuid4())
    divida = Divida.objects.get()
    cliente_logado.post(f"/dividas/{divida.pk}/baixa/")
    assert saldo_conta(corrente, ate=date(2026, 12, 31)) == antes
    assert not Lancamento.objects.exists()


def test_dar_baixa_e_reabrir_pela_tela(cliente_logado, divida):
    d = divida()
    cliente_logado.post(f"/dividas/{d.pk}/baixa/")
    d.refresh_from_db()
    assert d.paga and d.data_pagamento is not None
    assert cliente_logado.post(f"/dividas/{d.pk}/baixa/").status_code == 404  # já paga

    cliente_logado.post(f"/dividas/{d.pk}/reabrir/")
    d.refresh_from_db()
    assert (d.paga, d.data_pagamento) == (False, None)


def test_baixa_exige_post(cliente_logado, divida):
    d = divida()
    assert cliente_logado.get(f"/dividas/{d.pk}/baixa/").status_code == 405
    d.refresh_from_db()
    assert not d.paga


def test_resumo_soma_so_as_abertas_e_conta_vencidas(divida):
    divida(credor="A", valor_centavos=10_000, vencimento=date(2026, 9, 30))
    divida(credor="A", valor_centavos=5_000)
    divida(credor="B", valor_centavos=20_000, vencimento=date(2026, 12, 1))
    dar_baixa(divida(credor="C", valor_centavos=99_000), date(2026, 10, 2))
    resumo = resumir(hoje=date(2026, 10, 7))
    assert (resumo.total_aberto, resumo.quantidade_aberta, resumo.vencidas) == (35_000, 3, 1)
    assert [(c["credor"], c["total"]) for c in resumo.por_credor] == [("B", 20_000), ("A", 15_000)]


def test_banco_exige_data_de_pagamento_coerente(divida):
    with pytest.raises(IntegrityError):
        divida(paga=True, data_pagamento=None)


def test_reabrir_limpa_a_data(divida):
    d = dar_baixa(divida(), date(2026, 10, 1))
    reabrir(d)
    d.refresh_from_db()
    assert d.data_pagamento is None


def test_backup_inclui_dividas(divida):
    divida(credor="Credor Backup")
    dar_baixa(divida(credor="Credor Pago"), date(2026, 10, 1))
    pacote = exportar()
    Divida.objects.all().delete()
    importar(json.dumps(pacote).encode())
    assert sorted(Divida.objects.values_list("credor", "paga")) == [("Credor Backup", False), ("Credor Pago", True)]


def test_tela_abre_e_exige_login(client, cliente_logado, divida):
    divida(vencimento=date(2020, 1, 1))
    html = cliente_logado.get("/dividas/").content.decode()
    assert "Credor Fictício" in html and "vencida" in html
    client.post("/sair/")
    assert client.get("/dividas/").status_code == 302


# --- Aba "Por mês" -------------------------------------------------------

def test_agrupa_pelo_mes_da_data_da_divida(divida):
    from apps.dividas.services import agrupar_por_mes
    divida(credor="Nov A", valor_centavos=2_000, data=date(2026, 11, 30), vencimento=date(2026, 9, 1))
    divida(credor="Out", valor_centavos=4_000, data=date(2026, 10, 5))
    divida(credor="Nov B", valor_centavos=3_000, data=date(2026, 11, 2), vencimento=date(2027, 1, 1))
    grupos = agrupar_por_mes(Divida.objects.filter(paga=False))
    assert [(g.mes, g.total) for g in grupos] == [(date(2026, 10, 1), 4_000), (date(2026, 11, 1), 5_000)]
    assert [d.credor for d in grupos[1].dividas] == ["Nov B", "Nov A"]  # vencimento não influencia


def test_aba_por_mes_mostra_grupos_e_ignora_pagas(cliente_logado, divida):
    divida(credor="Credor Outubro", data=date(2026, 10, 5))
    dar_baixa(divida(credor="Credor Pago", data=date(2026, 10, 6)), date(2026, 10, 7))
    html = cliente_logado.get("/dividas/?visao=mes").content.decode()
    assert "Outubro de 2026" in html
    assert 'href="?visao=mes" aria-current="page"' in html
    secao = html.split('class="grupo-mes"')[1].split("<details")[0]  # até a lista de pagas
    assert "Credor Outubro" in secao and "Credor Pago" not in secao


def test_baixa_na_aba_por_mes_volta_para_ela(cliente_logado, divida):
    d = divida(vencimento=date(2026, 10, 5))
    resposta = cliente_logado.post(f"/dividas/{d.pk}/baixa/?visao=mes")
    assert resposta["Location"] == "/dividas/?visao=mes"


def test_visao_invalida_cai_na_lista(cliente_logado, db):
    html = cliente_logado.get("/dividas/?visao=xyz").content.decode()
    assert 'href="?visao=lista" aria-current="page"' in html
