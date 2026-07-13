from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.upload_cv, name="upload_cv"),
    path("analyse/", views.analyse_cv, name="ats_analyse"),
    path("analysis/", views.analyse_cv, name="ats_analysis"),
    path("result/<int:result_id>/", views.result_detail, name="ats_result"),
    path("result/<int:result_id>/download-cv/", views.download_generated_cv, name="download_generated_cv"),
    path("enterprise/bulk/", views.enterprise_bulk_upload, name="enterprise_bulk"),
    path("enterprise/report/<int:batch_id>/", views.enterprise_report, name="enterprise_report"),
    path("enterprise/report/<int:batch_id>/csv/", views.enterprise_report_csv, name="enterprise_report_csv"),
]
