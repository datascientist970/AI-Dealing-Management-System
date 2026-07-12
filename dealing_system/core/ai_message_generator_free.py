import google.generativeai as genai
from django.conf import settings
import json
import re
import random

# Configure Gemini
try:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
except:
    model = None

def generate_personalized_message_free(lead):
    """
    Generate personalized message using AI (Gemini)
    """
    
    lead_context = f"""
    Name: {lead.name}
    Phone: {lead.phone}
    Company: {lead.company or 'Not specified'}
    Status: {lead.get_status_display() if hasattr(lead, 'get_status_display') else 'New'}
    Source: {lead.source or 'Unknown'}
    Notes: {lead.notes or 'No notes'}
    """
    
    # Get previous interactions if any
    interactions_text = ""
    try:
        interactions = lead.interactions.order_by('-created_at')[:3]
        for idx, interaction in enumerate(interactions, 1):
            interactions_text += f"\n{idx}. Sent: {interaction.message[:50]}..."
            if interaction.response:
                interactions_text += f"\n   Response: {interaction.response[:50]}..."
    except:
        pass
    
    prompt = f"""
    You are an AI sales assistant. Generate a personalized WhatsApp message for this lead.
    
    LEAD INFO:
    {lead_context}
    
    PREVIOUS INTERACTIONS:
    {interactions_text if interactions_text else 'No previous interactions'}
    
    Rules:
    1. Message should be in Urdu or English (as appropriate)
    2. Max 100 words
    3. Be professional and friendly
    4. Include the lead's name
    5. Suggest a call to action
    
    Return ONLY the message, no additional text.
    """
    
    try:
        if model:
            response = model.generate_content(prompt)
            return {
                'message': response.text.strip(),
                'best_time': '10 AM - 12 PM',
                'response_probability': 'High' if lead.status == 'qualified' else 'Medium'
            }
        else:
            return get_fallback_message(lead)
    except Exception as e:
        print(f"AI Error: {e}")
        return get_fallback_message(lead)


def get_fallback_message(lead):
    """Fallback templates if AI fails"""
    templates = [
        f"Assalam-o-Alaikum {lead.name}! Hope you're doing well. I wanted to reach out regarding how we can help your business grow. Would you have 2 minutes for a quick chat?",
        
        f"Hello {lead.name}! I hope this message finds you well. We have some exciting updates that might interest {lead.company or 'you'}. Let me know when you're free to discuss.",
        
        f"Hi {lead.name}! Just checking in to see how things are going. Would you be interested in a quick call to explore how we can add value to your business?",
        
        f"Dear {lead.name}, I wanted to follow up on our previous conversation. Have you had a chance to think about what we discussed?",
        
        f"Assalam-o-Alaikum {lead.name}! {lead.company or 'Your business'} seems like a great fit for our services. Would you be available for a brief discussion this week?"
    ]
    
    # Pick based on lead ID
    template = templates[hash(lead.id) % len(templates)]
    return {
        'message': template,
        'best_time': '10 AM - 12 PM',
        'response_probability': 'Medium'
    }


def generate_bulk_messages_free(leads):
    """
    Generate AI messages for multiple leads
    """
    results = []
    
    for lead in leads:
        ai_response = generate_personalized_message_free(lead)
        results.append({
            'lead_id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'message': ai_response['message'],
            'best_time': ai_response['best_time'],
            'response_probability': ai_response['response_probability']
        })
    
    return results