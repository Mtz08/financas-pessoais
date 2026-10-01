from django.urls import path

from . import views

app_name = "contas"
urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.nova, name="nova"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/arquivar/", views.arquivar, name="arquivar"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
]
