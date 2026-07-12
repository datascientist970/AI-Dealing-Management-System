import time
import random
from datetime import datetime
from django.utils import timezone
from .whatsapp_free import send_whatsapp_message_free
from .ai_message_generator_free import generate_personalized_message_free
from .models import Lead, Interaction

def process_new_lead(lead):
    """
    Process a new lead automatically:
    1. AI analyzes lead data
    2. Generates personalized message
    3. Sends WhatsApp message
    """
    
    print(f"🤖 Processing lead: {lead.name}")
    
    try:
        # Step 1: AI Analysis
        print("📊 Step 1: AI Analyzing lead data...")
        ai_response = generate_personalized_message_free(lead)
        
        # Save AI analysis
        lead.ai_analysis = f"Best Time: {ai_response.get('best_time', 'N/A')}\n"
        lead.ai_analysis += f"Response Probability: {ai_response.get('response_probability', 'N/A')}\n"
        lead.ai_analysis += f"Generated Message: {ai_response.get('message', 'N/A')}"
        
        # Step 2: Get personalized message
        message = ai_response.get('message', '')
        lead.ai_message = message
        
        # Step 3: Send WhatsApp message
        print("📱 Step 2: Sending WhatsApp message...")
        result = send_whatsapp_message_free(lead.phone, message)
        
        # Step 4: Record interaction
        if result['success']:
            Interaction.objects.create(
                lead=lead,
                channel='whatsapp',
                phone_number_used='WhatsApp Web (Auto)',
                message=message,
                is_outgoing=True
            )
            
            lead.auto_message_sent = True
            lead.auto_message_date = timezone.now()
            lead.whatsapp_status = 'sent'
            lead.save()
            
            print(f"✅ Auto-message sent to {lead.name}")
            return {
                'success': True,
                'message': message,
                'lead': lead.name
            }
        else:
            lead.whatsapp_status = 'failed'
            lead.save()
            print(f"❌ Failed to send to {lead.name}: {result.get('error', 'Unknown error')}")
            return {
                'success': False,
                'error': result.get('error', 'Unknown error'),
                'lead': lead.name
            }
            
    except Exception as e:
        print(f"❌ Error processing {lead.name}: {str(e)}")
        lead.whatsapp_status = 'failed'
        lead.save()
        return {
            'success': False,
            'error': str(e),
            'lead': lead.name
        }


def process_bulk_leads(leads, delay=60):
    """
    Process multiple leads automatically
    """
    results = {
        'total': len(leads),
        'success': 0,
        'failed': 0,
        'details': []
    }
    
    for index, lead in enumerate(leads, 1):
        print(f"\n📨 Processing {index}/{len(leads)}: {lead.name}")
        
        result = process_new_lead(lead)
        
        if result['success']:
            results['success'] += 1
        else:
            results['failed'] += 1
        
        results['details'].append(result)
        
        # Delay between messages
        if index < len(leads):
            wait_time = random.randint(delay - 10, delay + 10)
            print(f"⏳ Waiting {wait_time} seconds before next message...")
            time.sleep(wait_time)
    
    return results


def auto_process_pending_leads():
    """
    Process all leads that haven't been auto-messaged yet
    """
    pending_leads = Lead.objects.filter(
        auto_message_sent=False,
        whatsapp_status='pending'
    )
    
    if pending_leads.exists():
        print(f"📋 Found {pending_leads.count()} pending leads to process")
        return process_bulk_leads(pending_leads)
    else:
        print("✅ No pending leads found")
        return {'total': 0, 'success': 0, 'failed': 0, 'details': []}