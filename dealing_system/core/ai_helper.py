import google.generativeai as genai
from django.conf import settings
import json
import re

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.1-lite-preview')

def get_gemini_suggestion(lead_data, interactions):
    """Get AI suggestions from Gemini for a lead"""
    
    # Prepare data for Gemini
    lead_info = f"""
    Lead Name: {lead_data.name}
    Phone: {lead_data.phone}
    Email: {lead_data.email or 'Not provided'}
    Company: {lead_data.company or 'Not provided'}
    Status: {lead_data.get_status_display()}
    Notes: {lead_data.notes or 'No notes'}
    """
    
    # Get recent interactions
    recent_interactions = interactions[:5] if interactions else []
    interaction_text = ""
    for idx, interaction in enumerate(recent_interactions, 1):
        interaction_text += f"""
        {idx}. Channel: {interaction.get_channel_display()}
           Message: {interaction.message}
           Response: {interaction.response or 'No response yet'}
           Date: {interaction.created_at.strftime('%Y-%m-%d %H:%M')}
        """
    
    prompt = f"""
    You are an AI sales assistant. Analyze this lead and provide suggestions:
    
    LEAD INFORMATION:
    {lead_info}
    
    RECENT INTERACTIONS:
    {interaction_text if interaction_text else 'No interactions yet'}
    
    Please provide:
    1. A personalized message to send to this lead (max 50 words)
    2. Best time to contact based on interaction patterns
    3. Suggested next step to close the deal
    4. What number to use (if multiple numbers, suggest the best one)
    5. How likely is this lead to convert? (High/Medium/Low)
    
    Format your response as JSON:
    {{
        "message": "Your personalized message",
        "best_time": "Best time suggestion",
        "next_step": "Suggested next step",
        "best_number": "Suggested number to use",
        "conversion_probability": "High/Medium/Low",
        "tips": "Additional tips for this lead"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result
        else:
            return {
                "message": "Hi! How can I help you today?",
                "best_time": "Morning hours (10 AM - 12 PM)",
                "next_step": "Schedule a follow-up call",
                "best_number": "Primary number",
                "conversion_probability": "Medium",
                "tips": "Build rapport and understand their needs"
            }
    except Exception as e:
        print(f"Gemini Error: {e}")
        return {
            "message": "Hi! How can I help you today?",
            "best_time": "Morning hours (10 AM - 12 PM)",
            "next_step": "Schedule a follow-up call",
            "best_number": "Primary number",
            "conversion_probability": "Medium",
            "tips": "Build rapport and understand their needs"
        }


def get_bulk_ai_insights(leads):
    """Get AI insights for multiple leads (for dashboard)"""
    
    leads_data = ""
    for lead in leads[:10]:  # Limit to 10 for performance
        leads_data += f"""
        - {lead.name} | {lead.phone} | Status: {lead.get_status_display()} | Interactions: {lead.interactions.count()}
        """
    
    prompt = f"""
    Analyze these leads and provide:
    1. Which leads need urgent attention (no interaction for 3+ days)
    2. Which leads are most likely to convert
    3. Overall team performance suggestions
    4. What's working and what's not
    
    LEADS DATA:
    {leads_data}
    
    Provide response as JSON:
    {{
        "urgent_leads": ["Lead1", "Lead2"],
        "hot_leads": ["Lead3", "Lead4"],
        "performance": "Overall performance assessment",
        "recommendations": ["Recommendation 1", "Recommendation 2"]
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            return {
                "urgent_leads": [],
                "hot_leads": [],
                "performance": "Good performance",
                "recommendations": ["Keep tracking leads regularly"]
            }
    except Exception as e:
        print(f"Gemini Error: {e}")
        return {
            "urgent_leads": [],
            "hot_leads": [],
            "performance": "Track your leads regularly",
            "recommendations": ["Use follow-up reminders"]
        }


def generate_email_content(lead_data, template_type='followup'):
    """Generate email content using Gemini"""
    
    templates = {
        'followup': f"""
        Subject: Following up with {lead_data.name}
        
        Hi {lead_data.name},
        
        I hope this email finds you well! I wanted to follow up on our recent conversation regarding how we can help your business grow.
        
        Have you had a chance to think about what we discussed? I'd love to hear your thoughts.
        
        Looking forward to your response!
        
        Best regards,
        [Your Team]
        """,
        
        'offer': f"""
        Subject: Special Offer for {lead_data.company}
        
        Dear {lead_data.name},
        
        We have an exciting offer for our valued partners like {lead_data.company}! This is a limited-time opportunity that we believe will bring great value to your business.
        
        Would you be available for a quick call to discuss this?
        
        Warm regards,
        [Your Team]
        """,
        
        'reminder': f"""
        Subject: Quick Reminder - {lead_data.name}
        
        Hi {lead_data.name},
        
        Just a friendly reminder about our upcoming discussion. Looking forward to connecting with you!
        
        Best,
        [Your Team]
        """
    }
    
    return templates.get(template_type, templates['followup'])