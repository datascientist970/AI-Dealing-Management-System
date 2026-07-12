from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Lead(models.Model):
    """Store all lead/customer data"""
    STATUS_CHOICES = [
        ('new', 'New Lead'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('lost', 'Lost'),
        ('converted', 'Converted - Deal Done'),
    ]
    
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    company = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    source = models.CharField(max_length=100, blank=True)  # Where did they come from?
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    auto_message_sent = models.BooleanField(default=False)
    auto_message_date = models.DateTimeField(null=True, blank=True)
    ai_analysis = models.TextField(blank=True, null=True)
    ai_message = models.TextField(blank=True, null=True)
    whatsapp_status = models.CharField(
        max_length=20, 
        choices=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('failed', 'Failed'),
            ('delivered', 'Delivered'),
            ('read', 'Read')
        ],
        default='pending'
    )

    
    def __str__(self):
        return f"{self.name} - {self.phone}"
    
    class Meta:
        ordering = ['-created_at']


class Interaction(models.Model):
    """Record every conversation/call/message"""
    CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('call', 'Phone Call'),
        ('email', 'Email'),
        ('sms', 'SMS'),
    ]
    
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='interactions')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    phone_number_used = models.CharField(max_length=20)  # Which number did you use?
    message = models.TextField()
    response = models.TextField(blank=True)
    is_outgoing = models.BooleanField(default=True)  # Did you send or receive?
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.lead.name} - {self.channel} - {self.created_at}"


class FollowUp(models.Model):
    """Follow-up reminders"""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='followups')
    reminder_date = models.DateTimeField()
    note = models.TextField()
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Follow up for {self.lead.name} - {self.reminder_date}"


class DailyReport(models.Model):
    """Daily performance tracking"""
    date = models.DateField(default=timezone.now)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    new_leads = models.IntegerField(default=0)
    interactions = models.IntegerField(default=0)
    conversions = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.date}"