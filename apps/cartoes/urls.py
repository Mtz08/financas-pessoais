from django.urls import path

from . import views

app_name = "cartoes"
urlpatterns = [
    path("", views.cartoes, name="index"),
    path("<int:conta_pk>/faturas/", views.faturas, name="faturas"),
    path("fatura/<int:pk>/", views.fatura, name="fatura"),
]
