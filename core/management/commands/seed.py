"""Popula o banco com dados FICTÍCIOS para testar o sistema.

Uso: python manage.py seed [--apagar]
"""

from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.backup.services import apagar_tudo
from apps.cartoes.models import Fatura
from apps.cartoes.pagamentos import pagar_fatura
from apps.cartoes.services import resumir_fatura
from apps.categorias.models import Categoria
from apps.contas.models import Conta
from apps.lancamentos.models import Lancamento
from apps.lancamentos.services.dados import DadosLancamento, DadosParcelamento, DadosTransferencia
from apps.lancamentos.services.lancamentos import criar_lancamento
from apps.lancamentos.services.parcelamentos import criar_parcelamento
from apps.lancamentos.services.recorrencias import DadosRecorrencia, criar_recorrencia
from apps.lancamentos.services.transferencias import criar_transferencia
from apps.orcamentos.models import Orcamento
from core import dates

CATEGORIAS = {
    "DESPESA": {
        "Moradia": ["Aluguel", "Condomínio", "Energia", "Internet"],
        "Alimentação": ["Mercado", "Restaurante", "Padaria"],
        "Transporte": ["Combustível", "Aplicativo", "Manutenção"],
        "Saúde": ["Farmácia", "Plano de saúde"],
        "Lazer": ["Streaming", "Passeios"],
        "Compras": ["Eletrodomésticos", "Vestuário"],
    },
    "RECEITA": {
        "Salário": [],
        "Rendimentos": [],
        "Outras receitas": [],
    },
}


class Command(BaseCommand):
    help = "Popula o banco com dados fictícios."

    def add_arguments(self, parser):
        parser.add_argument("--apagar", action="store_true", help="Apaga os dados atuais antes.")

    @transaction.atomic
    def handle(self, *args, apagar=False, **options):
        if not settings.DEBUG:
            raise CommandError("O seed só roda com DEBUG=True (nunca em produção).")
        if Conta.objects.exists():
            if not apagar:
                raise CommandError("Já existem dados. Use --apagar para substituir.")
            apagar_tudo()
        self.hoje = dates.hoje()
        self.inicio = dates.somar_meses(dates.primeiro_dia(self.hoje), -5)
        self._criar_categorias()
        self._criar_contas()
        self._criar_recorrencias()
        self._criar_lancamentos_avulsos()
        self._criar_parcelamentos()
        self._criar_orcamentos()
        self._pagar_faturas_vencidas()
        self.stdout.write(self.style.SUCCESS(f"Seed criado: {Lancamento.objects.count()} lançamentos fictícios."))

    def _criar_categorias(self):
        self.cat = {}
        for tipo, arvore in CATEGORIAS.items():
            for nome_pai, filhas in arvore.items():
                pai = Categoria.objects.create(nome=nome_pai, tipo=tipo)
                self.cat[nome_pai] = pai
                for nome in filhas:
                    self.cat[nome] = Categoria.objects.create(nome=nome, tipo=tipo, pai=pai)

    def _criar_contas(self):
        self.banco = Conta.objects.create(
            nome="Banco Exemplo", tipo="CORRENTE", saldo_inicial_centavos=350000, data_saldo_inicial=self.inicio
        )
        self.carteira = Conta.objects.create(
            nome="Carteira", tipo="CARTEIRA", saldo_inicial_centavos=15000, data_saldo_inicial=self.inicio
        )
        self.cartao = Conta.objects.create(
            nome="Cartão Exemplo", tipo="CARTAO", data_saldo_inicial=self.inicio,
            dia_fechamento=25, dia_vencimento=5, limite_centavos=800000,
        )

    def _criar_recorrencias(self):
        fixos = [
            ("RECEITA", self.banco, "Salário", "Salário Empresa Fictícia", 650000, 5),
            ("DESPESA", self.banco, "Aluguel", "Aluguel", 180000, 10),
            ("DESPESA", self.banco, "Internet", "Internet fibra", 11990, 15),
            ("DESPESA", self.cartao, "Streaming", "Assinatura streaming", 3990, 20),
            ("DESPESA", self.banco, "Energia", "Conta de luz", 21000, 31),  # testa dia 31
        ]
        for tipo, conta, categoria, descricao, valor, dia in fixos:
            criar_recorrencia(DadosRecorrencia(tipo, conta, self.cat[categoria], descricao, valor, dia, self.inicio))
        # Ocorrências passadas ficam pagas.
        Lancamento.objects.filter(recorrencia__isnull=False, data__lt=self.hoje).update(status="PAGO")

    def _criar_lancamentos_avulsos(self):
        exemplos = [
            (self.cartao, "Mercado", "Supermercado Fictício", [48750, 52310, 39990, 61200]),
            (self.cartao, "Restaurante", "Restaurante Exemplo", [8900, 12450, 7600]),
            (self.banco, "Combustível", "Posto Modelo", [22000, 19850]),
            (self.carteira, "Padaria", "Padaria da Esquina", [1850, 2300, 1575]),
            (self.cartao, "Farmácia", "Farmácia Teste", [4590]),
        ]
        for mes in dates.meses_entre(self.inicio, self.hoje):
            for conta, categoria, descricao, valores in exemplos:
                for dia, valor in zip((3, 12, 18, 26), valores, strict=False):
                    data = dates.data_no_mes(mes.year, mes.month, dia)
                    if data <= self.hoje:
                        self._despesa(conta, categoria, descricao, valor, data)
            saque = dates.data_no_mes(mes.year, mes.month, 7)
            if saque <= self.hoje:
                criar_transferencia(DadosTransferencia(self.banco, self.carteira, 10000, saque, "Saque"))

    def _despesa(self, conta, categoria, descricao, valor, data):
        status = "PAGO" if not conta.eh_cartao else "PENDENTE"
        criar_lancamento(DadosLancamento("DESPESA", conta, self.cat[categoria], descricao, valor, data, status))

    def _criar_parcelamentos(self):
        compras = [
            ("Geladeira", "Eletrodomésticos", 359990, 10, dates.somar_meses(self.hoje, -3)),
            ("Tênis de corrida", "Vestuário", 49990, 3, dates.somar_meses(self.hoje, -1)),
        ]
        for descricao, categoria, total, parcelas, data in compras:
            criar_parcelamento(DadosParcelamento(self.cartao, self.cat[categoria], descricao, total, parcelas, data))

    def _criar_orcamentos(self):
        limites = {"Alimentação": 150000, "Transporte": 50000, "Lazer": 20000, "Compras": 60000}
        for categoria, limite in limites.items():
            Orcamento.objects.create(categoria=self.cat[categoria], vigente_desde=self.inicio, limite_centavos=limite)

    def _pagar_faturas_vencidas(self):
        for fatura in Fatura.objects.filter(data_vencimento__lt=self.hoje):
            restante = resumir_fatura(fatura).restante_centavos
            if restante:
                pagar_fatura(fatura, self.banco, restante, fatura.data_vencimento)
