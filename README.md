# 📱 AI Dealing Management System

## Complete WhatsApp Automation + AI Lead Management


## 🎯 What is This System?

A complete **Dealing Management System** that helps you manage leads, track interactions, and send **automated WhatsApp messages** using AI.


## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI Lead Analysis** | Analyzes lead data and generates personalized messages |
| 📱 **WhatsApp Automation** | Send bulk WhatsApp messages (100% FREE - No Twilio) |
| 📊 **Bulk Import** | Import leads from Excel/CSV (Apollo.io compatible) |
| 📈 **Real-time Progress** | Live tracking of imports and message sending |
| 🔄 **Auto-Processing** | AI auto-analyzes and sends WhatsApp on lead add |
| 📋 **Daily Reports** | Track your daily performance |
| 📁 **Excel Export** | Export reports and lead data |


## 🚀 Quick Start

### 1. Installation

```bash
# Clone or download the project
cd dealing_system

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

```bash
# Create database tables
python manage.py makemigrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser
```

### 3. Run Server

```bash
python manage.py runserver
```

### 4. Access Application

```
http://127.0.0.1:8000/login/
```


## 📦 Requirements

```txt
Django>=5.2
pandas>=2.0.0
openpyxl>=3.1.0
pywhatkit==5.4
selenium>=4.0.0
webdriver-manager>=4.0.0
```

## 🎯 How It Works

### 1. Add Leads
- **Manually** → Add single lead with AI auto-processing
- **Bulk Import** → Upload Excel/CSV file

### 2. AI Auto-Processing
When a lead is added:
1. AI analyzes lead data
2. Generates personalized message
3. Sends WhatsApp message automatically

### 3. WhatsApp Setup (One-Time)
1. Go to **WhatsApp Setup** page
2. Click **Open WhatsApp Web**
3. Scan QR code from your phone
4. Click **Confirm Connection**

### 4. Bulk Messaging
1. Select leads
2. Click **Generate AI for All**
3. Click **Send Messages**

## 📁 Import File Format

### Compatible with Apollo.io Exports

| Column | Required |
|--------|----------|
| First Name | ✅ Yes |
| Last Name | ✅ Yes |
| Email | ✅ Yes |
| Corporate Phone | ✅ Yes |
| Company Name for Emails | Optional |
| Title | Optional |
| Seniority | Optional |
| Industry | Optional |


## 📱 WhatsApp Setup Guide

### Option 1: PyWhatKit (Recommended)
- **100% FREE**
- No Twilio required
- One-time QR scan
- Session auto-saved

### Option 2: Selenium (Alternative)
- More reliable
- Works with any browser
- Auto QR scanning

---

## 🛠️ Common Issues & Solutions

### Issue: "Country Code Missing"
**Solution:** Enter numbers in any format:
```
0300-1234567
+92-300-1234567
923001234567
```

### Issue: "WhatsApp Web not connected"
**Solution:**
1. Go to WhatsApp Setup page
2. Open WhatsApp Web
3. Scan QR code
4. Click "Check Connection"

### Issue: "DLL load failed while importing cygrpc"
**Solution:**
```bash
python -m pip uninstall google-generativeai
```
System will use fallback AI templates.

---

## ⚡ Quick Commands

```bash
# Run server
python manage.py runserver

# Create superuser
python manage.py createsuperuser

# Database reset
python manage.py flush

# Create migrations
python manage.py makemigrations
python manage.py migrate
```

## 📊 Features in Detail

### Dashboard
- Total leads count
- Today's new leads
- Conversion rate
- Pending follow-ups
- AI suggestions
- Weekly charts

### Lead Management
- Add/Edit/Delete leads
- Search and filter
- Status tracking
- Interaction history
- AI analysis per lead

### WhatsApp Automation
- Bulk WhatsApp messages
- AI-generated personalized messages
- Auto-delay to avoid ban
- Live progress tracking
- Failed message retry

### Reports
- Daily performance report
- Weekly analytics
- Export to Excel
- Print reports


## 🔒 Security

- User authentication required
- Session management
- SQLite database (upgrade to PostgreSQL)
- WhatsApp Web session encryption


## 📝 License

This project is for internal business use only.


## 🤝 Support

For issues or questions:
- Check the **WhatsApp Setup** page first
- Try **Chrome browser** for WhatsApp Web
- Ensure **stable internet connection**


## 🎉 Ready to Use!

System is fully functional. Start by:
1. Setting up WhatsApp Web
2. Adding your first lead
3. Sending AI-powered WhatsApp messages!

---

*Made with ❤️ for Dealing Management*
