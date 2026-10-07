from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Separada da anterior: no PostgreSQL, alterar a tabela na mesma transação
    do UPDATE gera "pending trigger events"."""

    dependencies = [
        ("categorias", "0002_dono"),
    ]

    operations = [
        migrations.AlterField(
            model_name="categoria",
            name="dono",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="categorias",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="categoria",
            name="categoria_raiz_nome_unico",
        ),
        migrations.AddConstraint(
            model_name="categoria",
            constraint=models.UniqueConstraint(
                condition=models.Q(("pai__isnull", True)),
                fields=("dono", "tipo", "nome"),
                name="categoria_raiz_nome_unico",
            ),
        ),
    ]
