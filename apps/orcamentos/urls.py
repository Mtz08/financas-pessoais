from django.urls import path

from . import views

app_name = "orcamentos"
urlpatterns = [
    path("", views.lista, name="lista"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
]
