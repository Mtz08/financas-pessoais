"""Gera as ocorrências futuras das recorrências (pode rodar via cron)."""

from django.core.management.base import BaseCommand

from apps.lancamentos.services.recorrencias import gerar_todas


class Command(BaseCommand):
    help = "Gera os lançamentos das recorrências até o horizonte configurado."

    def handle(self, *args, **options):
        self.stdout.write(f"{gerar_todas()} lançamento(s) gerado(s).")
