"""Isolamento entre usuários: ninguém vê, edita ou apaga dados de outro dono."""

import json
import uuid
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.backup.services import exportar, importar
from apps.cartoes.pagamentos import pagar_fatura
from apps.cartoes.services import fatura_da_compra
from apps.categorias.models import Categoria
from apps.contas.models import Conta
from apps.dividas.models import Divida
from apps.lancamentos.models import Lancamento, Recorrencia
from apps.lancamentos.services.dados import DadosLancamento, DadosTransferencia
from apps.lancamentos.services.lancamentos import criar_lancamento
from apps.lancamentos.services.recorrencias import DadosRecorrencia, criar_recorrencia
from apps.lancamentos.services.transferencias import criar_transferencia
from apps.orcamentos.models import Orcamento
from core import dates
from core.exceptions import RegraDeNegocio

from .conftest import SENHA_TESTE


@pytest.fixture
def dados_de_a(usuario, corrente, carteira, cartao, mercado, salario, despesa):
    """Usuário A (fixture `usuario`) com um pouco de tudo."""
    hoje = dates.hoje()
    lanc = criar_lancamento(despesa(descricao="Segredo de A", data=hoje))
    saida, _ = criar_transferencia(DadosTransferencia(corrente, carteira, 1_000, hoje, "Transferência de A"))
    compra = criar_lancamento(despesa(conta=cartao, descricao="Compra cartão de A", data=hoje, status="PENDENTE"))
    recorrencia = criar_recorrencia(DadosRecorrencia("DESPESA", corrente, mercado, "Aluguel de A", 50_000, 10, hoje))
    orcamento = Orcamento.objects.create(categoria=mercado.pai, vigente_desde=dates.primeiro_dia(hoje),
                                         limite_centavos=10_000)
    divida = Divida.objects.create(dono=usuario, credor="Credor de A", valor_centavos=7_000, data=hoje)
    divida_paga = Divida.objects.create(dono=usuario, credor="Credor pago de A", valor_centavos=1_000, data=hoje,
                                        paga=True, data_pagamento=hoje)
    return {"lanc": lanc, "saida": saida, "fatura": compra.fatura, "recorrencia": recorrencia, "orcamento": orcamento,
            "divida": divida, "divida_paga": divida_paga, "conta": corrente, "cartao": cartao,
            "categoria": mercado}


@pytest.fixture
def usuario_b(db):
    return User.objects.create_user("usuario_b", password=SENHA_TESTE)


@pytest.fixture
def cliente_b(usuario_b):
    cliente = Client()
    cliente.post("/entrar/", {"username": "usuario_b", "password": SENHA_TESTE})
    return cliente


# --- Telas: B não enxerga nada de A ----------------------------------------

@pytest.mark.parametrize("url", ["/", "/lancamentos/", "/lancamentos/recorrencias/", "/cartoes/", "/orcamentos/",
                                 "/relatorios/", "/contas/", "/categorias/", "/dividas/", "/dividas/?visao=mes",
                                 "/lancamentos/novo/despesa/", "/lancamentos/transferencia/nova/"])
def test_b_nao_ve_dados_de_a_em_nenhuma_tela(dados_de_a, cliente_b, url):
    html = cliente_b.get(url, follow=True).content.decode()
    for texto in ["Segredo de A", "Banco Teste", "Cartão Teste", "Alimentação", "Aluguel de A", "Credor de A",
                  "Transferência de A"]:
        assert texto not in html, (url, texto)


def test_csv_e_backup_de_b_nao_trazem_dados_de_a(dados_de_a, cliente_b, usuario_b):
    hoje = dates.hoje()
    csv = cliente_b.get(f"/relatorios/?inicio={hoje:%Y-%m-01}&fim={hoje}&formato=csv").content.decode("utf-8-sig")
    assert "Segredo de A" not in csv
    assert exportar(usuario_b)["dados"] == []
    assert "Segredo de A" not in cliente_b.get("/backup/baixar/").content.decode()


# --- Ações por ID: B recebe 404 e nada muda -------------------------------

def _rotas_de_a(d):
    return [
        ("get", f"/contas/{d['conta'].pk}/editar/"), ("post", f"/contas/{d['conta'].pk}/arquivar/"),
        ("post", f"/contas/{d['conta'].pk}/excluir/"),
        ("get", f"/categorias/{d['categoria'].pk}/editar/"), ("post", f"/categorias/{d['categoria'].pk}/arquivar/"),
        ("post", f"/categorias/{d['categoria'].pk}/excluir/"),
        ("get", f"/lancamentos/{d['lanc'].pk}/editar/"), ("get", f"/lancamentos/{d['lanc'].pk}/excluir/"),
        ("post", f"/lancamentos/{d['lanc'].pk}/excluir/"), ("post", f"/lancamentos/{d['lanc'].pk}/status/"),
        ("get", f"/lancamentos/transferencia/{d['saida'].pk}/editar/"),
        ("post", f"/lancamentos/recorrencias/{d['recorrencia'].pk}/encerrar/"),
        ("get", f"/cartoes/{d['cartao'].pk}/faturas/"), ("get", f"/cartoes/fatura/{d['fatura'].pk}/"),
        ("post", f"/orcamentos/{d['orcamento'].pk}/excluir/"),
        ("get", f"/dividas/{d['divida'].pk}/editar/"), ("post", f"/dividas/{d['divida'].pk}/baixa/"),
        ("post", f"/dividas/{d['divida_paga'].pk}/reabrir/"), ("post", f"/dividas/{d['divida'].pk}/excluir/"),
    ]


def test_b_recebe_404_em_todas_as_rotas_de_a(dados_de_a, cliente_b):
    antes = _fotografia()
    for metodo, url in _rotas_de_a(dados_de_a):
        resposta = getattr(cliente_b, metodo)(url)
        assert resposta.status_code == 404, (metodo, url, resposta.status_code)
    assert _fotografia() == antes  # nada de A foi alterado


def _fotografia():
    return (
        list(Conta.objects.values_list("id", "ativo").order_by("id")),
        list(Categoria.objects.values_list("id", "ativo").order_by("id")),
        list(Lancamento.objects.values_list("id", "status").order_by("id")),
        list(Recorrencia.objects.values_list("id", "data_fim").order_by("id")),
        list(Orcamento.objects.values_list("id").order_by("id")),
        list(Divida.objects.values_list("id", "paga").order_by("id")),
    )


def test_b_nao_consegue_lancar_na_conta_de_a_forcando_o_id(dados_de_a, cliente_b, usuario_b):
    categoria_b = Categoria.objects.create(dono=usuario_b, nome="Mercado B", tipo="DESPESA")
    resposta = cliente_b.post("/lancamentos/novo/despesa/", {
        "chave": str(uuid.uuid4()), "conta": dados_de_a["conta"].pk, "categoria": categoria_b.pk,
        "descricao": "Invasão", "valor": "10,00", "data": dates.hoje().isoformat(), "status": "PAGO"})
    assert resposta.status_code == 200  # formulário volta com "escolha inválida"
    assert not Lancamento.objects.filter(descricao="Invasão").exists()


def test_b_nao_paga_fatura_de_a_nem_com_conta_propria(dados_de_a, cliente_b, usuario_b):
    conta_b = Conta.objects.create(dono=usuario_b, nome="Conta B", tipo="CORRENTE", data_saldo_inicial=date(2026, 1, 1))
    resposta = cliente_b.post(f"/cartoes/fatura/{dados_de_a['fatura'].pk}/", {
        "chave": str(uuid.uuid4()), "conta_origem": conta_b.pk, "valor": "10,00", "data": dates.hoje().isoformat()})
    assert resposta.status_code == 404
    with pytest.raises(RegraDeNegocio):
        pagar_fatura(dados_de_a["fatura"], conta_b, 1_000, dates.hoje())


# --- Regras de negócio: nada mistura donos --------------------------------

def test_servicos_recusam_registros_de_donos_diferentes(dados_de_a, usuario_b):
    conta_b = Conta.objects.create(dono=usuario_b, nome="Conta B", tipo="CORRENTE", data_saldo_inicial=date(2026, 1, 1))
    with pytest.raises(RegraDeNegocio):
        criar_lancamento(DadosLancamento("DESPESA", conta_b, dados_de_a["categoria"], "Mistura", 100, date(2026, 3, 1)))
    with pytest.raises(RegraDeNegocio):
        criar_transferencia(DadosTransferencia(dados_de_a["conta"], conta_b, 100, date(2026, 3, 1)))


def test_mesmo_nome_pode_existir_em_usuarios_diferentes(dados_de_a, cliente_b):
    for url, dados in [
        ("/contas/nova/", {"nome": "Banco Teste", "tipo": "CORRENTE", "saldo_inicial_centavos": "0",
                           "data_saldo_inicial": "2026-01-01"}),
        ("/categorias/nova/", {"nome": "Alimentação", "tipo": "DESPESA"}),
    ]:
        assert cliente_b.post(url, {"chave": str(uuid.uuid4()), **dados}).status_code == 302, url
    assert Conta.objects.filter(nome="Banco Teste").count() == 2
    assert Categoria.objects.filter(nome="Alimentação", pai__isnull=True).count() == 2


def test_nome_repetido_do_mesmo_usuario_e_recusado_com_mensagem(dados_de_a, cliente_logado):
    resposta = cliente_logado.post("/contas/nova/", {
        "chave": str(uuid.uuid4()), "nome": "banco teste", "tipo": "CORRENTE", "saldo_inicial_centavos": "0",
        "data_saldo_inicial": "2026-01-01"})
    assert resposta.status_code == 200
    assert "Você já tem uma conta com esse nome." in resposta.content.decode()


# --- Backup: cada um mexe só no que é seu ---------------------------------

def test_importar_backup_de_a_na_conta_de_b_cria_copias_sem_tocar_em_a(dados_de_a, usuario, usuario_b):
    pacote = json.dumps(exportar(usuario)).encode()
    lancamentos_de_a = set(Lancamento.objects.do_usuario(usuario).values_list("id", flat=True))

    importar(usuario_b, pacote)
    importar(usuario_b, pacote)  # importar de novo substitui, não duplica

    assert set(Lancamento.objects.do_usuario(usuario).values_list("id", flat=True)) == lancamentos_de_a
    assert Lancamento.objects.do_usuario(usuario_b).count() == len(lancamentos_de_a)
    assert Lancamento.objects.do_usuario(usuario_b).filter(descricao="Segredo de A").exists()
    copia = Lancamento.objects.do_usuario(usuario_b).get(descricao="Segredo de A")
    assert copia.conta.dono == usuario_b and copia.categoria.dono == usuario_b
    # Transferência importada continua sendo um par, com identificador próprio.
    pares = Lancamento.objects.do_usuario(usuario_b).exclude(transferencia_id=None)
    assert pares.count() == 2 and len(set(pares.values_list("transferencia_id", flat=True))) == 1
    assert not pares.filter(transferencia_id=dados_de_a["saida"].transferencia_id).exists()


def test_backup_versao_1_do_sistema_antigo_continua_aceito(dados_de_a, usuario, usuario_b):
    pacote = exportar(usuario)
    pacote["versao"] = 1
    for registro in pacote["dados"]:
        registro["fields"].pop("dono", None)  # v1 não tinha dono
    importar(usuario_b, json.dumps(pacote).encode())
    assert Conta.objects.do_usuario(usuario_b).filter(nome="Banco Teste").exists()


def test_fatura_e_por_conta_de_cada_usuario(usuario, usuario_b, cartao):
    cartao_b = Conta.objects.create(dono=usuario_b, nome="Cartão Teste", tipo="CARTAO",
                                    data_saldo_inicial=date(2026, 1, 1), dia_fechamento=25, dia_vencimento=5)
    fa, fb = fatura_da_compra(cartao, date(2026, 3, 1)), fatura_da_compra(cartao_b, date(2026, 3, 1))
    assert fa.pk != fb.pk and fa.competencia == fb.competencia
