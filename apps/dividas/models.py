from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import ModeloComDatas, gerenciador_do_dono


class Divida(ModeloComDatas):
    """Lembrete de quanto você deve e a quem.

    Não é ligada a nenhuma conta: não entra em saldo, dashboard ou relatórios.
    A baixa é manual, quando você mesmo registra que pagou.
    """

    dono = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dividas")
    credor = models.CharField("Para quem devo", max_length=100)
    descricao = models.CharField("Descrição", max_length=120, blank=True)
    valor_centavos = models.BigIntegerField()
    data = models.DateField("Data da dívida")
    vencimento = models.DateField(null=True, blank=True)
    observacao = models.TextField("Observação", blank=True)
    paga = models.BooleanField(default=False)
    data_pagamento = models.DateField(null=True, blank=True)

    objects = gerenciador_do_dono("dono")

    class Meta:
        ordering = ["paga", models.F("vencimento").asc(nulls_last=True), "data", "id"]
        constraints = [
            models.CheckConstraint(name="divida_valor_positivo", condition=Q(valor_centavos__gt=0)),
            models.CheckConstraint(
                name="divida_baixa_consistente",
                condition=Q(paga=True, data_pagamento__isnull=False) | Q(paga=False, data_pagamento__isnull=True),
            ),
        ]

    def __str__(self):
        return f"{self.credor} — {self.descricao}" if self.descricao else self.credor
