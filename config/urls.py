from django.contrib import admin
from django.urls import path

from app import views

urlpatterns = [
    path("", views.index, name="index"),
    path("order/<int:id>", views.order_card, name="order_card"),
    path("item/<int:id>", views.item_card, name="item_card"),
    path("admin/", admin.site.urls),
    path(
        "payments/result/",
        views.payment_result,
        name="payment_result",
    ),
    path(
        "payments/create-intent/<str:resource_type>/<int:object_id>/",
        views.create_payment_intent,
        name="create_payment_intent",
    ),
]