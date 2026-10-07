from django.urls import path

from . import views

app_name = "dividas"
urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.nova, name="nova"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/baixa/", views.baixa, name="baixa"),
    path("<int:pk>/reabrir/", views.reabrir_divida, name="reabrir"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
]
