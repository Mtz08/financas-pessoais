import json
from datetime import date

import pytest

from apps.backup.services import exportar, importar
from apps.categorias.models import Categoria
from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento
from apps.lancamentos.services.dados import DadosParcelamento
from apps.lancamentos.services.lancamentos import criar_lancamento
from apps.lancamentos.services.parcelamentos import criar_parcelamento
from core.exceptions import RegraDeNegocio


@pytest.fixture
def dados_exemplo(corrente, cartao, mercado, despesa):
    criar_lancamento(despesa())
    criar_parcelamento(DadosParcelamento(cartao, mercado, "Sofá", 90_000, 3, date(2026, 2, 1)))


def _bytes(pacote) -> bytes:
    return json.dumps(pacote).encode()


def test_exportar_e_importar_restaura_tudo(dados_exemplo, usuario):
    pacote = exportar(usuario)
    antes = (Conta.objects.count(), Categoria.objects.count(), Lancamento.objects.count())
    Lancamento.objects.filter(parcelamento__isnull=True).delete()  # simula perda de dados

    importar(usuario, _bytes(pacote))

    assert (Conta.objects.count(), Categoria.objects.count(), Lancamento.objects.count()) == antes
    assert Categoria.objects.get(nome="Mercado").pai.nome == "Alimentação"
    novo = criar_lancamento(_dados_novos())
    assert novo.pk  # sequências de ID continuam funcionando


def _dados_novos():
    from apps.lancamentos.services.dados import DadosLancamento
    return DadosLancamento("DESPESA", Conta.objects.get(nome="Banco Teste"), Categoria.objects.get(nome="Mercado"),
                           "Após restaurar", 500, date(2026, 4, 1))


@pytest.mark.parametrize("conteudo", [b"nao e json", b"[]", _bytes({"formato": "outro", "versao": 1, "dados": []}),
                                      _bytes({"formato": "financas-backup", "versao": 99, "dados": []})])
def test_arquivo_invalido_e_recusado_sem_apagar_nada(dados_exemplo, usuario, conteudo):
    antes = Lancamento.objects.count()
    with pytest.raises(RegraDeNegocio):
        importar(usuario, conteudo)
    assert Lancamento.objects.count() == antes


def test_backup_adulterado_nao_cria_usuario(dados_exemplo, usuario):
    pacote = exportar(usuario)
    pacote["dados"].append({"model": "auth.user", "pk": 999,
                            "fields": {"username": "invasor", "password": "x", "is_superuser": True}})
    antes = Lancamento.objects.count()
    with pytest.raises(RegraDeNegocio):
        importar(usuario, _bytes(pacote))
    assert Lancamento.objects.count() == antes  # rollback completo
    from django.contrib.auth.models import User
    assert not User.objects.filter(username="invasor").exists()


def test_backup_com_referencia_quebrada_faz_rollback(dados_exemplo, usuario):
    pacote = exportar(usuario)
    for registro in pacote["dados"]:
        if registro["model"] == "lancamentos.lancamento":
            registro["fields"]["conta"] = 999_999
    antes = Lancamento.objects.count()
    with pytest.raises(RegraDeNegocio):
        importar(usuario, _bytes(pacote))
    assert Lancamento.objects.count() == antes
