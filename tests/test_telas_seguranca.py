"""Testes ponta a ponta via HTTP: login, CSRF, XSS, duplo envio, exclusão bloqueada."""

import uuid
from datetime import date

import pytest
from django.test import Client

from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento
from apps.lancamentos.services.lancamentos import criar_lancamento
from core import dates

from .conftest import SENHA_TESTE


def _post_despesa(cliente, conta, categoria, chave, **campos):
    dados = {"chave": str(chave), "conta": conta.pk, "categoria": categoria.pk, "descricao": "Mercado fictício",
             "valor": "1.234,56", "data": dates.hoje().isoformat(), "status": "PAGO", **campos}
    return cliente.post("/lancamentos/novo/despesa/", dados)


# --- Autenticação ---------------------------------------------------------

@pytest.mark.parametrize("url", ["/", "/lancamentos/", "/backup/baixar/", "/relatorios/?formato=csv"])
def test_paginas_exigem_login(client, db, url):
    resposta = client.get(url)
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_login_e_logout(client, usuario):
    resposta = client.post("/entrar/", {"username": usuario.username, "password": SENHA_TESTE})
    assert resposta.status_code == 302
    assert client.get("/").status_code == 200
    client.post("/sair/")
    assert client.get("/").status_code == 302


def test_senha_guardada_com_argon2(usuario):
    assert usuario.password.startswith("argon2")


def test_bloqueia_apos_5_tentativas_erradas(client, usuario):
    for _ in range(5):
        client.post("/entrar/", {"username": usuario.username, "password": "errada"})
    resposta = client.post("/entrar/", {"username": usuario.username, "password": SENHA_TESTE})
    assert resposta.status_code == 429  # bloqueado mesmo com a senha certa
    assert client.get("/").status_code == 302


# --- CSRF, XSS, CSP e redirecionamento ------------------------------------

def test_post_sem_token_csrf_e_recusado(usuario, corrente, mercado):
    cliente = Client(enforce_csrf_checks=True)
    cliente.force_login(usuario, backend="django.contrib.auth.backends.ModelBackend")
    resposta = _post_despesa(cliente, corrente, mercado, uuid.uuid4())
    assert resposta.status_code == 403
    assert not Lancamento.objects.exists()


def test_descricao_maliciosa_e_escapada_no_html(cliente_logado, despesa):
    criar_lancamento(despesa(descricao='<script>alert("x")</script>', data=dates.hoje()))
    html = cliente_logado.get("/lancamentos/").content.decode()
    assert '<script>alert("x")</script>' not in html
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html


def test_cabecalho_csp_bloqueia_script_inline(cliente_logado):
    csp = cliente_logado.get("/")["Content-Security-Policy"]
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp


def test_nao_redireciona_para_site_externo(cliente_logado, despesa):
    lancamento = criar_lancamento(despesa())
    resposta = cliente_logado.post(f"/lancamentos/{lancamento.pk}/status/", {"voltar": "https://exemplo-malicioso.test/"})
    assert resposta["Location"] == "/lancamentos/"


def test_csv_neutraliza_formulas(cliente_logado, despesa):
    criar_lancamento(despesa(descricao='=HYPERLINK("http://x.test")', data=date(2026, 3, 10)))
    csv = cliente_logado.get("/relatorios/?inicio=2026-03-01&fim=2026-03-31&formato=csv").content.decode("utf-8-sig")
    assert "'=HYPERLINK" in csv
    assert "-10,00" in csv  # vírgula decimal, despesa negativa


# --- Formulários ----------------------------------------------------------

def test_cria_despesa_com_valor_em_formato_brasileiro(cliente_logado, corrente, mercado):
    resposta = _post_despesa(cliente_logado, corrente, mercado, uuid.uuid4())
    assert resposta.status_code == 302
    assert Lancamento.objects.get().valor_centavos == 123456


def test_envio_duplicado_grava_uma_vez(cliente_logado, corrente, mercado):
    chave = uuid.uuid4()
    _post_despesa(cliente_logado, corrente, mercado, chave)
    resposta = _post_despesa(cliente_logado, corrente, mercado, chave)  # duplo clique / F5
    assert resposta.status_code == 302
    assert Lancamento.objects.count() == 1


def test_erro_de_regra_libera_a_chave_para_corrigir_e_reenviar(cliente_logado, corrente, mercado):
    chave = uuid.uuid4()
    resposta = _post_despesa(cliente_logado, corrente, mercado, chave, descricao="   ")
    assert resposta.status_code == 200  # formulário volta com erro
    _post_despesa(cliente_logado, corrente, mercado, chave)
    assert Lancamento.objects.count() == 1


@pytest.mark.parametrize("valor", ["12.5", "abc", "-10,00", "0,00"])
def test_valor_invalido_e_recusado_no_backend(cliente_logado, corrente, mercado, valor):
    resposta = _post_despesa(cliente_logado, corrente, mercado, uuid.uuid4(), valor=valor)
    assert resposta.status_code == 200
    assert not Lancamento.objects.exists()


def test_excluir_conta_com_lancamentos_e_bloqueado(cliente_logado, corrente, despesa):
    criar_lancamento(despesa())
    resposta = cliente_logado.post(f"/contas/{corrente.pk}/excluir/", follow=True)
    assert Conta.objects.filter(pk=corrente.pk).exists()
    assert "Arquive-o" in resposta.content.decode()


def test_conta_arquivada_some_dos_formularios_mas_mantem_historico(cliente_logado, corrente, despesa):
    lancamento = criar_lancamento(despesa())
    cliente_logado.post(f"/contas/{corrente.pk}/arquivar/")
    corrente.refresh_from_db()
    assert not corrente.ativo
    formulario = cliente_logado.get("/lancamentos/novo/despesa/").context["form"]
    assert corrente not in formulario.fields["conta"].queryset
    assert cliente_logado.get(f"/lancamentos/{lancamento.pk}/editar/").status_code == 200


def test_cartao_sem_dias_e_recusado_no_formulario(cliente_logado):
    resposta = cliente_logado.post("/contas/nova/", {
        "chave": str(uuid.uuid4()), "nome": "Cartão Novo", "tipo": "CARTAO", "saldo_inicial_centavos": "0",
        "data_saldo_inicial": "2026-01-01"})
    assert resposta.status_code == 200
    assert not Conta.objects.exists()


def test_editar_parcela_pela_tela_com_escopo(cliente_logado, corrente, mercado):
    from apps.lancamentos.services.dados import DadosParcelamento
    from apps.lancamentos.services.parcelamentos import criar_parcelamento

    parcelamento = criar_parcelamento(DadosParcelamento(corrente, mercado, "TV", 30_000, 3, date(2026, 1, 10)))
    segunda = parcelamento.parcelas.get(numero_parcela=2)
    cliente_logado.post(f"/lancamentos/{segunda.pk}/editar/", {
        "chave": str(uuid.uuid4()), "conta": corrente.pk, "categoria": mercado.pk, "descricao": "TV 50",
        "valor": "100,00", "data": "2026-02-10", "status": "PENDENTE", "escopo": "ESTA_E_PROXIMAS"})
    assert list(parcelamento.parcelas.order_by("numero_parcela").values_list("descricao", flat=True)) == [
        "TV", "TV 50", "TV 50"]


def test_todas_as_telas_abrem(cliente_logado, corrente, cartao, despesa):
    criar_lancamento(despesa(data=dates.hoje()))
    criar_lancamento(despesa(conta=cartao, data=dates.hoje()))
    for url in ["/", "/lancamentos/", "/lancamentos/novo/receita/", "/lancamentos/transferencia/nova/",
                "/lancamentos/parcelado/novo/", "/lancamentos/recorrencias/", "/lancamentos/recorrencias/nova/",
                "/cartoes/", "/orcamentos/", "/relatorios/", "/contas/", "/categorias/", "/backup/"]:
        assert cliente_logado.get(url, follow=True).status_code == 200, url
