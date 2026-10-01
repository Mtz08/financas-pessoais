from django.urls import path

from . import views

app_name = "backup"
urlpatterns = [
    path("", views.index, name="index"),
    path("baixar/", views.baixar, name="baixar"),
    path("restaurar/", views.restaurar, name="restaurar"),
]
