from django.urls import path

from . import views

app_name = "lancamentos"
urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/<str:tipo>/", views.novo, name="novo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path("<int:pk>/status/", views.alternar_status, name="alternar_status"),
    path("transferencia/nova/", views.transferencia_nova, name="transferencia_nova"),
    path("transferencia/<int:pk>/editar/", views.transferencia_editar, name="transferencia_editar"),
    path("parcelado/novo/", views.parcelado_novo, name="parcelado_novo"),
    path("recorrencias/", views.recorrencias, name="recorrencias"),
    path("recorrencias/nova/", views.recorrencia_nova, name="recorrencia_nova"),
    path("recorrencias/<int:pk>/encerrar/", views.recorrencia_encerrar, name="recorrencia_encerrar"),
]
