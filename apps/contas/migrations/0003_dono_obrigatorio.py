from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Separada da anterior: no PostgreSQL, alterar a tabela na mesma transação
    do UPDATE gera "pending trigger events"."""

    dependencies = [
        ("contas", "0002_dono"),
    ]

    operations = [
        migrations.AlterField(
            model_name="conta",
            name="dono",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="conta",
            name="nome",
            field=models.CharField(max_length=80),
        ),
        migrations.AddConstraint(
            model_name="conta",
            constraint=models.UniqueConstraint(fields=("dono", "nome"), name="conta_nome_unico_por_dono"),
        ),
    ]
