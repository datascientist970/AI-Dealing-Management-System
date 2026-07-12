from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Leads
    path('leads/', views.lead_list, name='lead_list'),
    path('leads/add/', views.add_lead, name='add_lead'),
    path('leads/<int:pk>/', views.lead_detail, name='lead_detail'),
    path('leads/<int:pk>/edit/', views.edit_lead, name='edit_lead'),
    path('leads/<int:pk>/delete/', views.delete_lead, name='delete_lead'),
    
    # Interactions
    path('leads/<int:lead_pk>/add-interaction/', views.add_interaction, name='add_interaction'),
    path('interaction/<int:pk>/delete/', views.delete_interaction, name='delete_interaction'),
    
    # Follow-ups
    path('leads/<int:lead_pk>/add-followup/', views.add_followup, name='add_followup'),
    path('followup/<int:pk>/complete/', views.complete_followup, name='complete_followup'),
    
    # Reports
    path('reports/daily/', views.daily_report, name='daily_report'),
    path('reports/ai-insights/', views.ai_insights, name='ai_insights'),
    path('reports/export/', views.export_report, name='export_report'),
    path('leads/import/', views.import_leads_excel, name='import_leads'),
    path('leads/download-sample/', views.download_sample_excel, name='download_sample_excel'),
    path('whatsapp/setup/', views.whatsapp_setup, name='whatsapp_setup'),
    path('whatsapp/check-session/', views.check_whatsapp_session_view, name='check_whatsapp_session'),
    path('whatsapp/status/', views.whatsapp_status_view, name='whatsapp_status'),
    
    # Free AI Bulk Messaging
    path('ai/bulk-messaging-free/', views.ai_bulk_messaging_free, name='ai_bulk_messaging_free'),
    path('ai/generate-message/<int:lead_id>/', views.generate_ai_message_ajax, name='generate_ai_message_ajax'),
     path('leads/process-pending/', views.process_all_pending, name='process_all_pending'),
    path('leads/retry-failed/', views.retry_failed_messages, name='retry_failed_messages'),
    path('api/lead-stats/', views.lead_stats_api, name='lead_stats_api'),
    path('whatsapp/status/', views.whatsapp_status_view, name='whatsapp_status'),
     path('whatsapp/confirm/', views.confirm_whatsapp_connection, name='confirm_whatsapp'),
    path('whatsapp/check-session/', views.check_whatsapp_session_view, name='check_whatsapp_session'),
    path('imports/progress/<str:session_id>/', views.get_import_progress, name='get_import_progress'),
    path('imports/cancel/<str:session_id>/', views.cancel_import, name='cancel_import'),

]