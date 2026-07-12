import pywhatkit as kit
import time
import random
from datetime import datetime
import os
import webbrowser
import sys
from pathlib import Path
import json
import re

# ===== Session Management =====

SESSION_FILE = Path.home() / '.whatsapp_session.json'

def save_session_status(connected=True):
    """Save WhatsApp session status manually"""
    try:
        with open(SESSION_FILE, 'w') as f:
            json.dump({
                'connected': connected,
                'timestamp': str(datetime.now())
            }, f)
        return True
    except:
        return False

def check_whatsapp_session():
    """Check if WhatsApp Web session exists"""
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, 'r') as f:
                data = json.load(f)
                if data.get('connected', False):
                    return True
        except:
            pass
    
    try:
        session_paths = [
            Path.home() / '.pywhatkit',
            Path.home() / '.config' / 'pywhatkit',
            Path(os.environ.get('APPDATA', '')) / 'pywhatkit',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'pywhatkit',
            Path.cwd() / '.pywhatkit',
        ]
        
        for path in session_paths:
            if path.exists():
                for file in path.iterdir():
                    if file.suffix in ['.pkl', '.json', '.dat'] and file.stat().st_size > 100:
                        return True
        return False
    except:
        return False


def open_whatsapp_web():
    """Open WhatsApp Web for QR code scanning"""
    webbrowser.open('https://web.whatsapp.com')
    return True


def confirm_whatsapp_connection():
    """Manually confirm that WhatsApp is connected"""
    return save_session_status(True)


def clean_phone_number(phone_number):
    """
    Clean and format phone number for PyWhatKit
    Important: PyWhatKit 5.4 requires format with '+'
    """
    # Remove all non-digit characters except +
    phone = re.sub(r'[^0-9]', '', phone_number)
    
    if not phone:
        return None, "Phone number is empty"
    
    # Pakistan format: +92XXXXXXXXXX (with +)
    if len(phone) == 10:
        # 03001234567 format
        phone = '+92' + phone
    elif len(phone) == 11 and phone.startswith('0'):
        # 03001234567 format
        phone = '+92' + phone[1:]
    elif len(phone) == 12 and phone.startswith('92'):
        # 923001234567 format
        phone = '+' + phone
    elif len(phone) == 13 and phone.startswith('92'):
        # 923001234567 format
        phone = '+' + phone
    else:
        # Try to fix
        if phone.startswith('0'):
            phone = '+92' + phone[1:]
        elif len(phone) >= 10 and not phone.startswith('92'):
            phone = '+92' + phone[-10:]
        elif phone.startswith('92'):
            phone = '+' + phone
    
    # Final validation
    if len(phone) < 10:
        return None, f"Invalid phone number: {phone_number}"
    
    return phone, None


def send_whatsapp_message_free(phone_number, message):
    """
    Send WhatsApp message using PyWhatKit 5.4
    ✅ Works with +923001234567 format
    """
    try:
        # Clean phone number - returns format with '+'
        phone, error = clean_phone_number(phone_number)
        
        if error:
            return {
                'success': False, 
                'error': error,
                'phone': phone_number
            }
        
        print(f"📱 Sending to: {phone} (Original: {phone_number})")
        
        # ✅ SEND USING + FORMAT (works in PyWhatKit 5.4)
        kit.sendwhatmsg_instantly(
            phone_no=phone,  # Format: +923001234567
            message=message,
            wait_time=15,  # Wait 15 seconds before sending
            tab_close=True,  # Close tab after sending
            close_time=3  # Close after 3 seconds
        )
        
        print(f"✅ Message sent to {phone_number}")
        return {'success': True, 'phone': phone_number}
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error sending to {phone_number}: {error_msg}")
        
        if 'not logged' in error_msg.lower() or 'qr' in error_msg.lower():
            return {
                'success': False, 
                'error': 'WhatsApp Web not connected. Please scan QR code first.',
                'need_login': True,
                'phone': phone_number
            }
        
        return {
            'success': False, 
            'error': error_msg, 
            'phone': phone_number
        }


def send_bulk_messages_free(leads, message_template, delay_range=(30, 60)):
    """Send bulk WhatsApp messages"""
    results = {
        'total': len(leads),
        'sent': 0,
        'failed': 0,
        'need_login': False,
        'details': []
    }
    
    for index, lead in enumerate(leads, 1):
        try:
            personalized_message = message_template
            personalized_message = personalized_message.replace('{name}', lead.name or 'Sir')
            personalized_message = personalized_message.replace('{phone}', lead.phone or '')
            personalized_message = personalized_message.replace('{company}', lead.company or 'your business')
            
            result = send_whatsapp_message_free(lead.phone, personalized_message)
            
            if result['success']:
                results['sent'] += 1
                try:
                    from .models import Interaction
                    Interaction.objects.create(
                        lead=lead,
                        channel='whatsapp',
                        phone_number_used='WhatsApp Web',
                        message=personalized_message,
                        is_outgoing=True
                    )
                except:
                    pass
            else:
                results['failed'] += 1
                if result.get('need_login'):
                    results['need_login'] = True
            
            results['details'].append({
                'name': lead.name,
                'phone': lead.phone,
                'status': 'Sent' if result['success'] else 'Failed',
                'error': result.get('error', '')
            })
            
            if index < len(leads):
                delay = random.randint(delay_range[0], delay_range[1])
                print(f"⏳ Waiting {delay} seconds before next message...")
                time.sleep(delay)
            
        except Exception as e:
            results['failed'] += 1
            results['details'].append({
                'name': lead.name,
                'phone': lead.phone,
                'status': 'Failed',
                'error': str(e)
            })
    
    return results


def get_whatsapp_status():
    """Get WhatsApp status"""
    return {
        'connected': check_whatsapp_session(),
        'session_file_exists': SESSION_FILE.exists()
    }


# ===== Test Function =====

def test_whatsapp_connection():
    """
    Test WhatsApp connection by sending a test message to yourself
    """
    print("🧪 Testing WhatsApp Connection...")
    print("📱 Make sure WhatsApp Web is connected")
    
    # Get your number
    test_number = input("Enter your phone number (with country code): ")
    test_message = "✅ Test message from Dealing AI System!"
    
    result = send_whatsapp_message_free(test_number, test_message)
    
    if result['success']:
        print("✅ Test successful! WhatsApp is working perfectly!")
    else:
        print(f"❌ Test failed: {result.get('error', 'Unknown error')}")
    
    return result