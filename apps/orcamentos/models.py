from django.db import models
from django.db.models import Q

from core.models import ModeloComDatas


class Orcamento(ModeloComDatas):
    """Limite mensal de gasto por categoria, válido a partir de `vigente_desde`.

    O limite de um mês M é o do registro com o maior `vigente_desde` <= M.
    Assim você define uma vez e só cria novo registro quando o valor mudar.
    Os alertas de 80% e 100% são calculados, não armazenados.
    """

    categoria = models.ForeignKey("categorias.Categoria", on_delete=models.PROTECT, related_name="orcamentos")
    vigente_desde = models.DateField(help_text="Dia 1º do primeiro mês de vigência.")
    limite_centavos = models.BigIntegerField()

    class Meta:
        ordering = ["categoria", "-vigente_desde"]
        constraints = [
            models.UniqueConstraint(fields=["categoria", "vigente_desde"], name="orcamento_unico_por_vigencia"),
            models.CheckConstraint(name="orcamento_limite_positivo", condition=Q(limite_centavos__gt=0)),
        ]

    def __str__(self):
        return f"{self.categoria} a partir de {self.vigente_desde:%m/%Y}"
