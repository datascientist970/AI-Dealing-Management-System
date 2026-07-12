from django.contrib import admin
from .models import Lead, Interaction, FollowUp, DailyReport

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'status', 'assigned_to', 'created_at']
    list_filter = ['status', 'source', 'created_at']
    search_fields = ['name', 'phone', 'email']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ['lead', 'channel', 'phone_number_used', 'created_at']
    list_filter = ['channel', 'created_at']

@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ['lead', 'reminder_date', 'is_completed']
    
@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'new_leads', 'interactions', 'conversions']