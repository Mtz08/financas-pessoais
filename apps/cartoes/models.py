from django.db import models
from django.db.models import F, Q

from core.models import ModeloComDatas, gerenciador_do_dono


class Fatura(ModeloComDatas):
    """Fatura mensal de um cartão.

    `competencia` é sempre o dia 1º do mês de vencimento (ex.: 2026-10-01).
    As datas de fechamento e vencimento ficam gravadas na fatura para que uma
    mudança futura no dia de fechamento do cartão não altere faturas antigas.
    O valor da fatura é a soma dos lançamentos ligados a ela (calculado).
    """

    conta = models.ForeignKey("contas.Conta", on_delete=models.PROTECT, related_name="faturas")
    competencia = models.DateField()
    data_fechamento = models.DateField()
    data_vencimento = models.DateField()

    objects = gerenciador_do_dono("conta__dono")

    class Meta:
        ordering = ["conta", "competencia"]
        constraints = [
            models.UniqueConstraint(fields=["conta", "competencia"], name="fatura_unica_por_mes"),
            models.CheckConstraint(
                name="fatura_fecha_antes_de_vencer", condition=Q(data_fechamento__lt=F("data_vencimento"))
            ),
        ]

    def __str__(self):
        return f"{self.conta} — {self.competencia:%m/%Y}"
