from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path("upload/", views.upload_cv, name="upload_cv"),
    path("cv/<uuid:public_id>/edit/", views.update_cv, name="update_cv"),
    path("cv/<uuid:public_id>/delete/", views.delete_cv, name="delete_cv"),
    path("analyse/", views.analyse_cv, name="ats_analyse"),
    path("analysis/", RedirectView.as_view(pattern_name="ats_analyse", permanent=True), name="ats_analysis"),
    path("result/<int:result_id>/", views.result_detail, name="ats_result"),
    path("result/<int:result_id>/download-cv/", views.download_generated_cv, name="download_generated_cv"),
    path("result/<int:result_id>/bullet-review/start/", views.start_bullet_review, name="start_bullet_review"),
    path("result/<int:result_id>/bullet-review/apply/", views.apply_bullet_review, name="apply_bullet_review"),
    path("result/<int:result_id>/bullet-review/<int:suggestion_id>/", views.decide_bullet_suggestion, name="decide_bullet_suggestion"),
    path("result/<int:result_id>/save-cv-draft/", views.save_generated_cv_draft, name="save_generated_cv_draft"),
    path("result/<int:result_id>/download-cv-docx/", views.download_generated_cv_docx, name="download_generated_cv_docx"),
    path("result/<int:result_id>/download-cover-letter/", views.download_cover_letter, name="download_cover_letter"),
    path("enterprise/bulk/", views.enterprise_bulk_upload, name="enterprise_bulk"),
    path("enterprise/report/<int:batch_id>/", views.enterprise_report, name="enterprise_report"),
    path("enterprise/report/<int:batch_id>/csv/", views.enterprise_report_csv, name="enterprise_report_csv"),
]
