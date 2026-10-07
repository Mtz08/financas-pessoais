from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.dashboard.views import index as dashboard

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("entrar/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("contas/", include("apps.contas.urls")),
    path("categorias/", include("apps.categorias.urls")),
    path("lancamentos/", include("apps.lancamentos.urls")),
    path("cartoes/", include("apps.cartoes.urls")),
    path("orcamentos/", include("apps.orcamentos.urls")),
    path("relatorios/", include("apps.relatorios.urls")),
    path("dividas/", include("apps.dividas.urls")),
    path("backup/", include("apps.backup.urls")),
]
