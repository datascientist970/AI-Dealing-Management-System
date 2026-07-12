from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
import pandas as pd
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from .models import Lead, Interaction, FollowUp, DailyReport
from collections import Counter
import json
from .import_progress import ImportProgressTracker
import threading
import uuid
import tempfile
import os
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

# ===== Import WhatsApp Functions =====
from .whatsapp_free import (
    send_bulk_messages_free, 
    open_whatsapp_web, 
    check_whatsapp_session,
    get_whatsapp_status,
    send_whatsapp_message_free
)

# ===== AI Helper Functions (Fallback if ai_helper.py doesn't exist) =====

def get_ai_suggestions(lead):
    """Generate AI-powered suggestions"""
    suggestions = []
    
    last_interaction = lead.interactions.order_by('-created_at').first()
    if last_interaction:
        days_since = (timezone.now() - last_interaction.created_at).days
        if days_since > 3:
            suggestions.append(f"No follow-up with {lead.name} for {days_since} days! Contact now.")
    
    used_numbers = lead.interactions.values_list('phone_number_used', flat=True)
    if used_numbers:
        freq = Counter(used_numbers)
        least_used = min(freq, key=freq.get)
        suggestions.append(f"Try {least_used} for better response rate.")
    
    if lead.status == 'new':
        suggestions.append("Send intro message to start conversation.")
    elif lead.status == 'contacted':
        suggestions.append("Ask if they have any questions about your offer.")
    elif lead.status == 'qualified':
        suggestions.append("Hot lead! Schedule a meeting to close the deal.")
    
    return suggestions

def generate_ai_message(lead):
    """Auto-generate message"""
    messages_list = [
        f"Hi {lead.name}, hope you're doing well! How can I help you today?",
        f"Hi {lead.name}, I wanted to follow up on our previous conversation.",
        f"Hi {lead.name}, we have some exciting updates to share with you.",
        f"Hi {lead.name}, are you free for a quick chat this week?"
    ]
    return messages_list[hash(lead.id) % len(messages_list)]

def get_best_phone_number(lead):
    """Suggest best number to use"""
    used_numbers = lead.interactions.values_list('phone_number_used', flat=True)
    if not used_numbers:
        return "Any number - first contact"
    freq = Counter(used_numbers)
    least_used = min(freq, key=freq.get)
    return f"{least_used} (used only {freq[least_used]} times)"

def get_gemini_suggestion(lead, interactions):
    """Get Gemini AI suggestions (fallback if ai_helper not available)"""
    try:
        from .ai_helper import get_gemini_suggestion as gemini_suggestion
        return gemini_suggestion(lead, interactions)
    except ImportError:
        # Fallback suggestions
        return {
            'message': f"Hi {lead.name}! How can I help you today?",
            'best_time': 'Morning hours (10 AM - 12 PM)',
            'next_step': 'Schedule a follow-up call',
            'best_number': get_best_phone_number(lead),
            'conversion_probability': 'Medium',
            'tips': 'Build rapport and understand their needs'
        }

def generate_email_content(lead, template_type='followup'):
    """Generate email content (fallback if ai_helper not available)"""
    try:
        from .ai_helper import generate_email_content as email_gen
        return email_gen(lead, template_type)
    except ImportError:
        templates = {
            'followup': f"""
Subject: Following up with {lead.name}

Hi {lead.name},

I hope this email finds you well! I wanted to follow up on our recent conversation regarding how we can help your business grow.

Have you had a chance to think about what we discussed? I'd love to hear your thoughts.

Looking forward to your response!

Best regards,
[Your Team]
""",
            'offer': f"""
Subject: Special Offer for {lead.company}

Dear {lead.name},

We have an exciting offer for our valued partners like {lead.company}! This is a limited-time opportunity that we believe will bring great value to your business.

Would you be available for a quick call to discuss this?

Warm regards,
[Your Team]
""",
            'reminder': f"""
Subject: Quick Reminder - {lead.name}

Hi {lead.name},

Just a friendly reminder about our upcoming discussion. Looking forward to connecting with you!

Best,
[Your Team]
"""
        }
        return templates.get(template_type, templates['followup'])

# ===== Authentication Views =====

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'core/auth/login.html')

@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')

# ===== Dashboard =====

@login_required
def dashboard(request):
    today = timezone.now().date()
    
    # Stats
    total_leads = Lead.objects.count()
    new_leads_today = Lead.objects.filter(created_at__date=today).count()
    converted_total = Lead.objects.filter(status='converted').count()
    converted_today = Lead.objects.filter(status='converted', updated_at__date=today).count()
    pending_followups = FollowUp.objects.filter(is_completed=False, reminder_date__date=today).count()
    total_interactions = Interaction.objects.count()
    interactions_today = Interaction.objects.filter(created_at__date=today).count()
    
    # AI - Critical leads (no interaction for 3+ days)
    critical_leads = []
    for lead in Lead.objects.filter(status__in=['new', 'contacted']):
        last = lead.interactions.order_by('-created_at').first()
        if last:
            days = (timezone.now() - last.created_at).days
            if days >= 3:
                lead.days_inactive = days
                critical_leads.append(lead)
        else:
            lead.days_inactive = 999
            critical_leads.append(lead)
    critical_leads = critical_leads[:5]
    
    # AI Suggestions (global)
    all_leads = Lead.objects.filter(status__in=['new', 'contacted'])[:3]
    ai_suggestions = []
    for lead in all_leads:
        if lead.interactions.count() == 0:
            ai_suggestions.append(f"💡 {lead.name} - No interaction yet. Send welcome message.")
        elif lead.interactions.last() and (timezone.now() - lead.interactions.last().created_at).days > 2:
            ai_suggestions.append(f"⏰ {lead.name} - Pending follow-up for {(timezone.now() - lead.interactions.last().created_at).days} days.")
    
    if not ai_suggestions:
        ai_suggestions = ["✅ All leads are being tracked properly!", "💡 Great job staying on top of your leads!"]
    
    # Recent leads
    recent_leads = Lead.objects.order_by('-created_at')[:10]
    
    # Chart data - Last 7 days
    chart_data = []
    for i in range(7, -1, -1):
        date = today - timedelta(days=i)
        chart_data.append({
            'date': date.strftime('%d/%m'),
            'leads': Lead.objects.filter(created_at__date=date).count(),
            'interactions': Interaction.objects.filter(created_at__date=date).count()
        })
    
    # WhatsApp Status
    whatsapp_connected = check_whatsapp_session()
    
    context = {
        'total_leads': total_leads,
        'new_leads_today': new_leads_today,
        'converted_total': converted_total,
        'converted_today': converted_today,
        'pending_followups': pending_followups,
        'total_interactions': total_interactions,
        'interactions_today': interactions_today,
        'critical_leads': critical_leads,
        'ai_suggestions': ai_suggestions,
        'recent_leads': recent_leads,
        'chart_labels': json.dumps([d['date'] for d in chart_data]),
        'chart_leads': json.dumps([d['leads'] for d in chart_data]),
        'chart_interactions': json.dumps([d['interactions'] for d in chart_data]),
        'whatsapp_connected': whatsapp_connected,
    }
    return render(request, 'core/dashboard/index.html', context)

# ===== Lead Management =====

@login_required
def lead_list(request):
    leads = Lead.objects.all().order_by('-created_at')
    status_filter = request.GET.get('status')
    if status_filter:
        leads = leads.filter(status=status_filter)
    
    paginator = Paginator(leads, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'leads': page_obj,
        'status_filter': status_filter,
    }
    return render(request, 'core/leads/list.html', context)

@login_required
def lead_detail(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    interactions = lead.interactions.order_by('-created_at')
    followups = lead.followups.filter(is_completed=False)
    
    # Get AI suggestions
    try:
        ai_suggestion = get_gemini_suggestion(lead, interactions)
        email_content = generate_email_content(lead, 'followup')
    except Exception as e:
        print(f"AI Error: {e}")
        ai_suggestion = {
            'message': f"Hi {lead.name}! How can I help you today?",
            'best_time': 'Morning hours (10 AM - 12 PM)',
            'next_step': 'Schedule a follow-up call',
            'best_number': 'Primary number',
            'conversion_probability': 'Medium',
            'tips': 'Build rapport and understand their needs'
        }
        email_content = f"""
Subject: Following up with {lead.name}

Hi {lead.name},

I hope this email finds you well! I wanted to follow up on our recent conversation.

Looking forward to your response!

Best regards,
[Your Team]
"""
    
    # Get best number suggestion
    used_numbers = lead.interactions.values_list('phone_number_used', flat=True).distinct()
    best_number = get_best_phone_number(lead)
    
    context = {
        'lead': lead,
        'interactions': interactions,
        'followups': followups,
        'ai_suggestion': ai_suggestion,
        'email_content': email_content,
        'best_number': best_number,
        'used_numbers': used_numbers,
    }
    return render(request, 'core/leads/detail.html', context)

@login_required
def add_lead(request):
    users = User.objects.all()
    
    if request.method == 'POST':
        lead = Lead()
        lead.name = request.POST.get('name')
        lead.phone = request.POST.get('phone')
        lead.email = request.POST.get('email')
        lead.company = request.POST.get('company')
        lead.source = request.POST.get('source')
        lead.status = request.POST.get('status', 'new')
        lead.notes = request.POST.get('notes')
        assigned_to_id = request.POST.get('assigned_to')
        if assigned_to_id:
            lead.assigned_to = User.objects.get(id=assigned_to_id)
        lead.save()
        
        # Auto process with AI and WhatsApp
        auto_send = request.POST.get('auto_send', 'on') == 'on'
        
        if auto_send:
            messages.info(request, f'🤖 AI is analyzing {lead.name}...')
            try:
                from .auto_processor import process_new_lead
                result = process_new_lead(lead)
                if result['success']:
                    messages.success(request, f'✅ WhatsApp message sent to {lead.name}!')
                else:
                    messages.warning(request, f'⚠️ Lead added but message failed: {result.get("error", "Unknown error")}')
            except Exception as e:
                messages.warning(request, f'⚠️ Lead added but auto-processing failed: {str(e)}')
        else:
            messages.success(request, f'✅ Lead {lead.name} added successfully!')
        
        return redirect('lead_detail', pk=lead.id)
    
    whatsapp_connected = check_whatsapp_session()
    context = {
        'users': users,
        'whatsapp_connected': whatsapp_connected,
    }
    return render(request, 'core/leads/add.html', context)

@login_required
def edit_lead(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    users = User.objects.all()
    
    if request.method == 'POST':
        lead.name = request.POST.get('name')
        lead.phone = request.POST.get('phone')
        lead.email = request.POST.get('email')
        lead.company = request.POST.get('company')
        lead.source = request.POST.get('source')
        lead.status = request.POST.get('status')
        lead.notes = request.POST.get('notes')
        assigned_to_id = request.POST.get('assigned_to')
        if assigned_to_id:
            lead.assigned_to = User.objects.get(id=assigned_to_id)
        else:
            lead.assigned_to = None
        lead.save()
        
        messages.success(request, f'Lead {lead.name} updated successfully!')
        return redirect('lead_detail', pk=lead.id)
    
    context = {'lead': lead, 'users': users}
    return render(request, 'core/leads/edit.html', context)

@login_required
def delete_lead(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    name = lead.name
    lead.delete()
    messages.success(request, f'Lead {name} deleted successfully!')
    return redirect('lead_list')

# ===== Interactions =====

@login_required
def add_interaction(request, lead_pk):
    lead = get_object_or_404(Lead, pk=lead_pk)
    
    if request.method == 'POST':
        interaction = Interaction()
        interaction.lead = lead
        interaction.channel = request.POST.get('channel')
        interaction.phone_number_used = request.POST.get('phone_number_used')
        interaction.message = request.POST.get('message')
        interaction.response = request.POST.get('response')
        interaction.is_outgoing = request.POST.get('is_outgoing') == 'on'
        interaction.save()
        
        # Update lead status
        if interaction.channel == 'call' and lead.status == 'new':
            lead.status = 'contacted'
            lead.save()
        
        messages.success(request, 'Interaction recorded successfully!')
        return redirect('lead_detail', pk=lead_pk)
    
    context = {'lead': lead}
    return render(request, 'core/interactions/add.html', context)

@login_required
def delete_interaction(request, pk):
    interaction = get_object_or_404(Interaction, pk=pk)
    lead_pk = interaction.lead.id
    interaction.delete()
    messages.success(request, 'Interaction deleted!')
    return redirect('lead_detail', pk=lead_pk)

# ===== Follow-ups =====

@login_required
def add_followup(request, lead_pk):
    lead = get_object_or_404(Lead, pk=lead_pk)
    
    if request.method == 'POST':
        followup = FollowUp()
        followup.lead = lead
        followup.reminder_date = request.POST.get('reminder_date')
        followup.note = request.POST.get('note')
        followup.save()
        
        messages.success(request, 'Follow-up reminder added!')
        return redirect('lead_detail', pk=lead_pk)
    
    return redirect('lead_detail', pk=lead_pk)

@login_required
def complete_followup(request, pk):
    followup = get_object_or_404(FollowUp, pk=pk)
    lead_pk = followup.lead.id
    followup.is_completed = True
    followup.save()
    
    messages.success(request, 'Follow-up marked as complete!')
    return redirect('lead_detail', pk=lead_pk)

# ===== WhatsApp Views =====

@login_required
def whatsapp_setup(request):
    """One-time WhatsApp Web setup page"""
    is_connected = check_whatsapp_session()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'open_whatsapp':
            open_whatsapp_web()
            messages.info(request, '📱 WhatsApp Web opened! Scan QR code from your phone.')
            return redirect('whatsapp_setup')
        
        elif action == 'check_connection':
            is_connected = check_whatsapp_session()
            if is_connected:
                messages.success(request, '✅ WhatsApp Web is connected! You can now send messages.')
                return redirect('dashboard')
            else:
                messages.warning(request, '⚠️ Still not connected. Please scan the QR code.')
                return redirect('whatsapp_setup')
    
    context = {
        'whatsapp_connected': is_connected
    }
    return render(request, 'core/whatsapp_setup.html', context)


@login_required
def check_whatsapp_session_view(request):
    """AJAX view to check WhatsApp Web session"""
    try:
        is_connected = check_whatsapp_session()
        return JsonResponse({
            'connected': is_connected,
            'success': is_connected,
            'message': 'Connected' if is_connected else 'Not Connected'
        })
    except Exception as e:
        return JsonResponse({
            'connected': False,
            'success': False,
            'message': str(e),
            'error': str(e)
        })

@login_required
def whatsapp_status_view(request):
    """Check WhatsApp Web status"""
    status = get_whatsapp_status()
    return JsonResponse(status)


@login_required
def ai_bulk_messaging_free(request):
    """Free AI bulk messaging page"""
    leads = Lead.objects.filter(status__in=['new', 'contacted', 'qualified'])
    whatsapp_connected = check_whatsapp_session()
    
    if request.method == 'POST':
        lead_ids = request.POST.getlist('lead_ids')
        message_type = request.POST.get('message_type', 'ai')
        delay = int(request.POST.get('delay', 60))
        
        if not lead_ids:
            messages.error(request, 'Please select at least one lead')
            return redirect('ai_bulk_messaging_free')
        
        selected_leads = Lead.objects.filter(id__in=lead_ids)
        
        if message_type == 'ai':
            # Generate AI messages
            from .ai_message_generator_free import generate_bulk_messages_free
            bulk_messages = generate_bulk_messages_free(selected_leads)
            
            # Send each message
            for lead, msg_data in zip(selected_leads, bulk_messages):
                result = send_bulk_messages_free([lead], msg_data['message'], (delay, delay+10))
                if result['sent'] > 0:
                    messages.success(request, f'✅ Message sent to {lead.name}!')
                else:
                    messages.error(request, f'❌ Failed to send to {lead.name}')
        else:
            # Template message
            template = request.POST.get('template_message', '')
            if not template:
                messages.error(request, 'Please enter a template message')
                return redirect('ai_bulk_messaging_free')
            
            result = send_bulk_messages_free(selected_leads, template, (delay, delay+10))
            messages.success(request, f'📱 Messages sent: {result["sent"]} sent, {result["failed"]} failed')
        
        return redirect('lead_list')
    
    context = {
        'leads': leads,
        'total_leads': leads.count(),
        'whatsapp_connected': whatsapp_connected,
        'ai_ready': leads.filter(interactions__isnull=False).distinct().count()
    }
    return render(request, 'core/ai_bulk_messaging_free.html', context)


@login_required
def generate_ai_message_ajax(request, lead_id):
    """AJAX endpoint to generate AI message for a single lead"""
    lead = get_object_or_404(Lead, pk=lead_id)
    from .ai_message_generator_free import generate_personalized_message_free
    result = generate_personalized_message_free(lead)
    return JsonResponse(result)


@login_required
def lead_stats_api(request):
    """API endpoint for lead statistics"""
    return JsonResponse({
        'pending': Lead.objects.filter(auto_message_sent=False, whatsapp_status='pending').count(),
        'failed': Lead.objects.filter(whatsapp_status='failed').count(),
        'sent': Lead.objects.filter(whatsapp_status='sent').count(),
        'total': Lead.objects.count()
    })


# ===== Process Pending =====

@login_required
def process_all_pending(request):
    """Process all leads that haven't been auto-messaged yet"""
    if request.method == 'POST':
        from .auto_processor import auto_process_pending_leads
        result = auto_process_pending_leads()
        
        messages.success(
            request,
            f'✅ Processed {result["total"]} leads. '
            f'📱 {result["success"]} messages sent, {result["failed"]} failed.'
        )
        return redirect('dashboard')
    
    pending_count = Lead.objects.filter(auto_message_sent=False, whatsapp_status='pending').count()
    
    context = {
        'pending_count': pending_count
    }
    return render(request, 'core/process_pending.html', context)


@login_required
def retry_failed_messages(request):
    """Retry failed WhatsApp messages"""
    if request.method == 'POST':
        from .auto_processor import process_bulk_leads
        failed_leads = Lead.objects.filter(whatsapp_status='failed')
        
        if not failed_leads.exists():
            messages.info(request, 'No failed messages to retry')
            return redirect('dashboard')
        
        result = process_bulk_leads(failed_leads)
        
        messages.success(
            request,
            f'✅ Retried {result["total"]} leads. '
            f'📱 {result["success"]} sent successfully, {result["failed"]} still failed.'
        )
        return redirect('dashboard')
    
    failed_count = Lead.objects.filter(whatsapp_status='failed').count()
    
    context = {
        'failed_count': failed_count
    }
    return render(request, 'core/retry_failed.html', context)


# ===== Reports =====

@login_required
def daily_report(request):
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    # Get or create today's report
    report, created = DailyReport.objects.get_or_create(
        user=request.user,
        date=today
    )
    report.new_leads = Lead.objects.filter(assigned_to=request.user, created_at__date=today).count()
    report.interactions = Interaction.objects.filter(lead__assigned_to=request.user, created_at__date=today).count()
    report.conversions = Lead.objects.filter(assigned_to=request.user, status='converted', updated_at__date=today).count()
    report.save()
    
    # Weekly data
    weekly_reports = DailyReport.objects.filter(
        user=request.user,
        date__gte=week_ago
    ).order_by('date')
    
    week_labels = [r.date.strftime('%d/%m') for r in weekly_reports]
    week_leads = [r.new_leads for r in weekly_reports]
    week_interactions = [r.interactions for r in weekly_reports]
    
    # Totals
    weekly_total_leads = sum(week_leads)
    weekly_total_interactions = sum(week_interactions)
    weekly_conversions = sum([r.conversions for r in weekly_reports])
    
    # Recent interactions
    recent_interactions = Interaction.objects.filter(
        lead__assigned_to=request.user
    ).order_by('-created_at')[:20]
    
    context = {
        'today': today,
        'report': report,
        'week_labels': json.dumps(week_labels),
        'week_leads': json.dumps(week_leads),
        'week_interactions': json.dumps(week_interactions),
        'weekly_total_leads': weekly_total_leads,
        'weekly_total_interactions': weekly_total_interactions,
        'weekly_conversions': weekly_conversions,
        'recent_interactions': recent_interactions,
    }
    return render(request, 'core/reports/daily.html', context)


@login_required
def ai_insights(request):
    """AI Insights page with advanced analytics"""
    leads = Lead.objects.all()
    
    # Stats
    total_leads = leads.count()
    converted = leads.filter(status='converted').count()
    conversion_rate = (converted / total_leads * 100) if total_leads > 0 else 0
    
    # Lead distribution by status
    status_counts = leads.values('status').annotate(count=Count('status'))
    
    # Top performing sources
    source_stats = leads.values('source').annotate(count=Count('id')).order_by('-count')[:5]
    
    # Active vs inactive
    active_leads = Lead.objects.filter(
        interactions__created_at__gte=timezone.now() - timedelta(days=7)
    ).distinct().count()
    
    # Pending follow-ups
    pending_followups = FollowUp.objects.filter(is_completed=False).count()
    
    context = {
        'total_leads': total_leads,
        'converted': converted,
        'conversion_rate': round(conversion_rate, 2),
        'active_leads': active_leads,
        'status_counts': status_counts,
        'source_stats': source_stats,
        'pending_followups': pending_followups,
    }
    return render(request, 'core/ai_insights.html', context)


# ===== Excel Export =====

@login_required
def export_report(request):
    """Export daily report to Excel"""
    date_str = request.GET.get('date')
    if date_str:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        report_date = timezone.now().date()
    
    # Get data for the date
    leads = Lead.objects.filter(created_at__date=report_date)
    interactions = Interaction.objects.filter(created_at__date=report_date)
    
    # Create Excel workbook
    wb = Workbook()
    
    # Sheet 1: Leads
    ws1 = wb.active
    ws1.title = "Leads"
    
    # Headers
    headers = ['Name', 'Phone', 'Email', 'Company', 'Status', 'Source', 'Created At']
    for col, header in enumerate(headers, 1):
        cell = ws1.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4e73df", end_color="4e73df", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Data
    for row, lead in enumerate(leads, 2):
        ws1.cell(row=row, column=1, value=lead.name)
        ws1.cell(row=row, column=2, value=lead.phone)
        ws1.cell(row=row, column=3, value=lead.email or '')
        ws1.cell(row=row, column=4, value=lead.company or '')
        ws1.cell(row=row, column=5, value=lead.get_status_display())
        ws1.cell(row=row, column=6, value=lead.source or '')
        ws1.cell(row=row, column=7, value=lead.created_at.strftime('%Y-%m-%d %H:%M'))
    
    # Sheet 2: Interactions
    ws2 = wb.create_sheet("Interactions")
    
    # Headers
    headers2 = ['Lead', 'Channel', 'Phone Used', 'Message', 'Response', 'Direction', 'Created At']
    for col, header in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1cc88a", end_color="1cc88a", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Data
    for row, interaction in enumerate(interactions, 2):
        ws2.cell(row=row, column=1, value=interaction.lead.name)
        ws2.cell(row=row, column=2, value=interaction.get_channel_display())
        ws2.cell(row=row, column=3, value=interaction.phone_number_used)
        ws2.cell(row=row, column=4, value=interaction.message)
        ws2.cell(row=row, column=5, value=interaction.response or '')
        ws2.cell(row=row, column=6, value='Outgoing' if interaction.is_outgoing else 'Incoming')
        ws2.cell(row=row, column=7, value=interaction.created_at.strftime('%Y-%m-%d %H:%M'))
    
    # Auto-adjust column widths
    for sheet in [ws1, ws2]:
        for column in sheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            sheet.column_dimensions[column_letter].width = adjusted_width
    
    # Response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="daily_report_{report_date.strftime("%Y-%m-%d")}.xlsx"'
    wb.save(response)
    
    return response


# ===== Excel Import =====
@login_required
def import_leads_excel(request):
    """Import leads from Excel file with real-time progress"""
    
    if request.method == 'POST' and request.FILES.get('excel_file'):
        try:
            excel_file = request.FILES['excel_file']
            
            # ✅ Save file to temporary location
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f'import_{uuid.uuid4().hex}.xlsx')
            
            with open(temp_path, 'wb+') as destination:
                for chunk in excel_file.chunks():
                    destination.write(chunk)
            
            # Generate unique session ID
            session_id = str(uuid.uuid4())[:8]
            tracker = ImportProgressTracker(session_id)
            
            # ✅ Start background processing with file path
            thread = threading.Thread(
                target=process_import_in_background,
                args=(request.user.id, temp_path, session_id)
            )
            thread.daemon = True
            thread.start()
            
            # Return session ID for progress tracking
            return render(request, 'core/import_progress.html', {
                'session_id': session_id,
                'file_name': excel_file.name
            })
            
        except Exception as e:
            messages.error(request, f'Error starting import: {str(e)}')
            return redirect('import_leads')
    
    return render(request, 'core/leads/import.html')


def process_import_in_background(user_id, file_path, session_id):
    """Process import in background thread"""
    
    from django.contrib.auth.models import User
    from django.db import connection
    
    tracker = ImportProgressTracker(session_id)
    
    try:
        # ✅ Get user (create new DB connection for thread)
        user = User.objects.get(id=user_id)
        
        # ✅ Read file from temp location
        if file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
        
        # ✅ Clean up temp file
        try:
            os.remove(file_path)
        except:
            pass
        
        # Filter and prepare data
        leads_data = []
        total_phone_numbers = 0
        
        # Check for phone column
        phone_column = None
        for col in ['Corporate Phone', 'Phone', 'Mobile', 'Phone Number', 'phone']:
            if col in df.columns:
                phone_column = col
                break
        
        if not phone_column:
            tracker.error('No phone column found in the file')
            return
        
        # Check for email column
        email_column = None
        for col in ['Email', 'Email Address', 'E-mail', 'email']:
            if col in df.columns:
                email_column = col
                break
        
        # Process each row
        total_rows = len(df)
        tracker.start(total_rows)
        
        imported_count = 0
        skipped_count = 0
        duplicate_count = 0
        failed_count = 0
        processed = 0
        
        # Process in batches for speed
        for index, row in df.iterrows():
            processed += 1
            
            try:
                # Get phone number
                phone = ''
                if pd.notna(row.get(phone_column)):
                    phone = str(row.get(phone_column, '')).strip()
                    # Clean phone number
                    import re
                    phone = re.sub(r'[^0-9+]', '', phone)
                
                # Skip if no phone
                if not phone or len(phone) < 5:
                    skipped_count += 1
                    tracker.update(processed, imported_count, failed_count, skipped_count, duplicate_count, f'Row {index+1} - No phone', '')
                    continue
                
                # Get email
                email = ''
                if email_column and pd.notna(row.get(email_column)):
                    email = str(row.get(email_column, '')).strip()
                
                # Skip if no email
                if not email:
                    skipped_count += 1
                    tracker.update(processed, imported_count, failed_count, skipped_count, duplicate_count, f'Row {index+1} - No email', phone)
                    continue
                
                # Check duplicate
                existing = Lead.objects.filter(
                    Q(email=email) | Q(phone=phone)
                ).first()
                
                if existing:
                    duplicate_count += 1
                    tracker.update(processed, imported_count, failed_count, skipped_count, duplicate_count, f'Duplicate: {email}', phone)
                    continue
                
                # Create lead
                lead = Lead()
                
                # Name
                first_name = str(row.get('First Name', '')).strip() if 'First Name' in df.columns and pd.notna(row.get('First Name')) else ''
                last_name = str(row.get('Last Name', '')).strip() if 'Last Name' in df.columns and pd.notna(row.get('Last Name')) else ''
                lead.name = f"{first_name} {last_name}".strip() or 'Unknown'
                
                # Phone and Email
                lead.phone = phone[:20]
                lead.email = email[:200]
                
                # Company
                company_col = 'Company Name for Emails' if 'Company Name for Emails' in df.columns else 'Company'
                lead.company = str(row.get(company_col, ''))[:200] if company_col in df.columns and pd.notna(row.get(company_col)) else ''
                
                # Source
                lead.source = 'Apollo.io Import'
                
                # Status based on Seniority
                seniority = str(row.get('Seniority', '')).lower() if 'Seniority' in df.columns and pd.notna(row.get('Seniority')) else ''
                if 'c suite' in seniority or 'director' in seniority or 'vp' in seniority or 'head' in seniority:
                    lead.status = 'qualified'
                elif 'manager' in seniority or 'senior' in seniority:
                    lead.status = 'contacted'
                else:
                    lead.status = 'new'
                
                # Notes
                notes = []
                for col in ['Title', 'Departments', 'Seniority', 'Technologies', 'Industry', 'Country']:
                    if col in df.columns and pd.notna(row.get(col)):
                        value = str(row.get(col, ''))
                        if value:
                            notes.append(f"{col}: {value[:200]}")
                
                lead.notes = '\n'.join(notes) if notes else ''
                
                # Assign to current user
                lead.assigned_to = user
                
                lead.save()
                imported_count += 1
                
                # Update progress
                tracker.update(processed, imported_count, failed_count, skipped_count, duplicate_count, lead.name, phone)
                
                # ✅ Close DB connection periodically to avoid timeout
                if processed % 50 == 0:
                    connection.close()
                
            except Exception as e:
                failed_count += 1
                tracker.update(processed, imported_count, failed_count, skipped_count, duplicate_count, f'Error: {str(e)[:30]}', '')
        
        # Complete
        tracker.complete(imported_count, failed_count, skipped_count, duplicate_count)
        
        # Auto-process imported leads
        if imported_count > 0:
            try:
                from .auto_processor import process_bulk_leads
                new_leads = Lead.objects.filter(
                    source='Apollo.io Import',
                    auto_message_sent=False
                )[:imported_count]
                
                if new_leads.exists():
                    result = process_bulk_leads(new_leads)
            except Exception as e:
                print(f"Auto-process error: {e}")
                
    except Exception as e:
        tracker.error(str(e))
        # Clean up temp file on error
        try:
            os.remove(file_path)
        except:
            pass

@login_required
def get_import_progress(request, session_id):
    """AJAX endpoint to get import progress"""
    data = ImportProgressTracker.get_progress(session_id)
    
    if data:
        # Format estimated time
        if data.get('estimated_time') and data['estimated_time'] > 0:
            minutes = data['estimated_time'] // 60
            seconds = data['estimated_time'] % 60
            if minutes > 0:
                data['estimated_time_text'] = f'{minutes}m {seconds}s'
            else:
                data['estimated_time_text'] = f'{seconds}s'
        else:
            data['estimated_time_text'] = 'Calculating...'
        
        # Count phone numbers
        data['phone_count'] = len(data.get('phone_numbers', []))
        
        return JsonResponse(data)
    
    return JsonResponse({'status': 'not_found'}, status=404)


@login_required
def cancel_import(request, session_id):
    """Cancel import process"""
    ImportProgressTracker.clear(session_id)
    return JsonResponse({'status': 'cancelled'})


@login_required
def download_sample_excel(request):
    """Download sample Excel template (Apollo.io compatible)"""
    from openpyxl.styles import Font, PatternFill
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Apollo Leads"
    
    # Headers matching Apollo.io format
    headers = [
        'First Name', 'Last Name', 'Title', 'Company Name for Emails',
        'Email', 'Corporate Phone', 'Seniority', 'Departments',
        '# Employees', 'Industry', 'Country', 'Company City',
        'Company Address', 'Company Phone', 'Technologies'
    ]
    
    # Add headers with formatting
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4e73df", end_color="4e73df", fill_type="solid")
    
    # Sample data
    sample_data = [
        ['John', 'Doe', 'VP of Sales', 'ABC Corp', 'john@abc.com', '+92 300 1234567', 'Director', 'Sales', '500', 'Technology', 'Saudi Arabia', 'Riyadh', '123 Main St', '+966 11 234 5678', 'AWS, Salesforce'],
        ['Jane', 'Smith', 'HR Manager', 'XYZ Ltd', 'jane@xyz.com', '+92 300 7654321', 'Manager', 'Human Resources', '200', 'Real Estate', 'Saudi Arabia', 'Jeddah', '456 Park Ave', '+966 12 345 6789', 'Google Workspace, Slack'],
        ['Ahmed', 'Khan', 'CEO', 'Tech Solutions', 'ahmed@tech.com', '+92 300 9876543', 'C-Suite', 'Executive', '50', 'IT Services', 'Saudi Arabia', 'Dammam', '789 Business Bay', '+966 13 456 7890', 'Azure, Python'],
    ]
    
    for row_idx, row_data in enumerate(sample_data, 2):
        for col_idx, value in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col_idx, value=value)
    
    # Auto-adjust column widths
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 30)
        ws.column_dimensions[column].width = adjusted_width
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="apollo_leads_import_template.xlsx"'
    wb.save(response)
    
    return response
    
@login_required
def confirm_whatsapp_connection(request):
    """Manually confirm WhatsApp connection"""
    from .whatsapp_free import confirm_whatsapp_connection, check_whatsapp_session
    
    if request.method == 'POST':
        confirm_whatsapp_connection()
        messages.success(request, '✅ WhatsApp connection confirmed! You can now send messages.')
        return redirect('dashboard')
    
    is_connected = check_whatsapp_session()
    return render(request, 'core/confirm_whatsapp.html', {'whatsapp_connected': is_connected})


@login_required
def check_whatsapp_session_view(request):
    """AJAX view to check WhatsApp Web session"""
    from .whatsapp_free import check_whatsapp_session
    is_connected = check_whatsapp_session()
    return JsonResponse({
        'connected': is_connected,
        'success': is_connected,
        'message': 'Connected' if is_connected else 'Not Connected'
    })