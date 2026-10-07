from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def atribuir_ao_primeiro_usuario(apps, schema_editor):
    """Registros que já existiam (sistema de um usuário só) passam a ser do
    primeiro usuário cadastrado."""
    Modelo = apps.get_model("categorias", "Categoria")
    if not Modelo.objects.exists():
        return
    Usuario = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    dono = Usuario.objects.order_by("id").first()
    if dono is None:
        raise RuntimeError(
            "Existem registros sem dono e nenhum usuário cadastrado. "
            "Crie um usuário (createsuperuser) e rode o migrate de novo."
        )
    Modelo.objects.update(dono=dono)


class Migration(migrations.Migration):

    dependencies = [
        ("categorias", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="categoria",
            name="dono",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="categorias",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(atribuir_ao_primeiro_usuario, migrations.RunPython.noop),
    ]
