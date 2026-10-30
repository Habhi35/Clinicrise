from django.urls import path
from reports.views import (
    MonthlyGrowthReportDetailView,
    MonthlyGrowthReportGenerateView,
    MonthlyGrowthReportLatestPDFView,
    MonthlyGrowthReportListView,
    MonthlyGrowthReportPDFDownloadView,
)

app_name = 'reports'

urlpatterns = [
    # Monthly Growth Reports
    path('monthly/', MonthlyGrowthReportListView.as_view(), name='monthly_reports_list'),
    path('monthly/generate/', MonthlyGrowthReportGenerateView.as_view(), name='monthly_report_generate'),
    path('monthly/latest/pdf/', MonthlyGrowthReportLatestPDFView.as_view(), name='monthly_report_latest_pdf'),
    path('monthly/<uuid:pk>/', MonthlyGrowthReportDetailView.as_view(), name='monthly_report_detail'),
    path('monthly/<uuid:pk>/pdf/', MonthlyGrowthReportPDFDownloadView.as_view(), name='monthly_report_pdf'),
]
