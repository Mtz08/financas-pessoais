from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.models import ModeloArquivavel

DIA_DO_MES = [MinValueValidator(1), MaxValueValidator(31)]


class Conta(ModeloArquivavel):
    """Conta corrente, carteira (dinheiro) ou cartão de crédito.

    Saldo = saldo_inicial + entradas - saídas (calculado, nunca armazenado,
    para não haver dois "fontes da verdade" que possam divergir).
    Para cartão, saldo negativo significa valor devido.
    """

    class Tipo(models.TextChoices):
        CORRENTE = "CORRENTE", "Conta corrente"
        CARTEIRA = "CARTEIRA", "Dinheiro em espécie"
        CARTAO = "CARTAO", "Cartão de crédito"

    nome = models.CharField(max_length=80, unique=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    saldo_inicial_centavos = models.BigIntegerField(default=0)
    data_saldo_inicial = models.DateField()
    # Só para cartão de crédito:
    dia_fechamento = models.PositiveSmallIntegerField(null=True, blank=True, validators=DIA_DO_MES)
    dia_vencimento = models.PositiveSmallIntegerField(null=True, blank=True, validators=DIA_DO_MES)
    limite_centavos = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["nome"]
        constraints = [
            models.CheckConstraint(
                name="conta_cartao_exige_dias",
                condition=(
                    Q(tipo="CARTAO", dia_fechamento__isnull=False, dia_vencimento__isnull=False)
                    | Q(~Q(tipo="CARTAO"), dia_fechamento__isnull=True, dia_vencimento__isnull=True,
                        limite_centavos__isnull=True)
                ),
            ),
            models.CheckConstraint(
                name="conta_dias_validos",
                condition=(
                    Q(dia_fechamento__isnull=True) | Q(dia_fechamento__gte=1, dia_fechamento__lte=31)
                ) & (
                    Q(dia_vencimento__isnull=True) | Q(dia_vencimento__gte=1, dia_vencimento__lte=31)
                ),
            ),
            models.CheckConstraint(
                name="conta_limite_positivo",
                condition=Q(limite_centavos__isnull=True) | Q(limite_centavos__gt=0),
            ),
        ]

    def __str__(self):
        return self.nome

    @property
    def eh_cartao(self) -> bool:
        return self.tipo == self.Tipo.CARTAO
