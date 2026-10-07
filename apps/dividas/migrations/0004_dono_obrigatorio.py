from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Separada da anterior: no PostgreSQL, alterar a tabela na mesma transação
    do UPDATE gera "pending trigger events"."""

    dependencies = [
        ("dividas", "0003_dono"),
    ]

    operations = [
        migrations.AlterField(
            model_name="divida",
            name="dono",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dividas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
