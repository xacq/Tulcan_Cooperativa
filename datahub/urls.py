from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.upload_data, name="upload_data"),
    path("batches/", views.batches, name="batches"),

    path("customers/", views.customers_list, name="customers_list"),
    path("customers/<str:cliente>/", views.customer_detail, name="customer_detail"),
    path("customers/<str:cliente>/edit/", views.customer_edit, name="customer_edit"),
    path("customers/<str:cliente>/toggle/", views.customer_toggle_active, name="customer_toggle_active"),
    path("customers/<str:cliente>/score/", views.customer_score, name="customer_score"),

    path("operations/", views.operations_list, name="operations_list"),
]
