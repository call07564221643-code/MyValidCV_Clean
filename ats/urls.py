from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.upload_cv, name="upload_cv"),
    path("analyse/", views.analyse_cv, name="ats_analyse"),
    path("result/<int:result_id>/", views.result_detail, name="ats_result"),
]