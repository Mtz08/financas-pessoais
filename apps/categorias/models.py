from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import ModeloArquivavel, gerenciador_do_dono


class Categoria(ModeloArquivavel):
    """Categoria com no máximo dois níveis: Moradia > Aluguel."""

    class Tipo(models.TextChoices):
        RECEITA = "RECEITA", "Receita"
        DESPESA = "DESPESA", "Despesa"

    dono = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="categorias")
    nome = models.CharField(max_length=60)
    tipo = models.CharField(max_length=7, choices=Tipo.choices)
    pai = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,  # não exclui categoria que tem subcategorias
        null=True,
        blank=True,
        related_name="subcategorias",
    )

    objects = gerenciador_do_dono("dono")

    class Meta:
        ordering = ["tipo", "pai__nome", "nome"]
        constraints = [
            # Nome único entre irmãs; o segundo índice cobre as categorias raiz
            # (em SQL, NULL != NULL, então o primeiro sozinho não bastaria).
            models.UniqueConstraint(fields=["pai", "nome"], name="categoria_nome_unico_no_pai"),
            models.UniqueConstraint(
                fields=["dono", "tipo", "nome"], condition=Q(pai__isnull=True), name="categoria_raiz_nome_unico"
            ),
            models.CheckConstraint(name="categoria_nao_e_pai_de_si", condition=~Q(pai=models.F("id"))),
        ]

    def __str__(self):
        return f"{self.pai.nome} > {self.nome}" if self.pai_id else self.nome

    def clean(self):
        if self.pai_id is None:
            return
        if self.pai.pai_id is not None:
            raise ValidationError({"pai": "Só são permitidos dois níveis (categoria > subcategoria)."})
        if self.pai.tipo != self.tipo:
            raise ValidationError({"pai": "A subcategoria deve ter o mesmo tipo da categoria pai."})
