# Email Service Integration - Complete System Overview

## Branch: `feature/email-service`

This document explains what was implemented on the `feature/email-service` branch and how it completes the integration with the `fastapi-migration` branch to create a complete email engagement and referral system.

---

## Overview

The `feature/email-service` branch implements the **email sending infrastructure** that works in conjunction with the business logic on `fastapi-migration`. This branch is **read-only** - it only reads data from the shared MongoDB database to determine who to email, then sends personalized emails.

---

## What Was Implemented

### 1. Engagement Reader Service (`app/services/engagement_reader_service.py`)

**Purpose:** Read-only service that queries the database to identify users who should receive different types of emails.

**Key Methods:**

#### `get_new_users(hours_ago=1)`
- **What it does:** Finds users registered in the last N hours
- **Used for:** Welcome emails (sent 1 hour after registration)
- **Reads from:** `User` collection (created_at timestamp)

#### `get_inactive_users()`
- **What it does:** Finds users with no chat activity in the last 3+ days
- **Used for:** Re-engagement emails
- **Reads from:** `User` and `Conversation` collections (last_message_at)

#### `get_active_users_for_engagement()`
- **What it does:** Finds users with 5+ chats who haven't provided engagement info
- **Used for:** Engagement form emails
- **Reads from:** `Conversation` (message_count) and `UserEngagement` (checks if info exists)

#### `get_users_for_curated_emails()`
- **What it does:** Finds users who provided engagement info and should get personalized tips
- **Used for:** Daily curated emails with personalized content
- **Reads from:** `UserEngagement` collection (use_case, profession, interests)

#### `get_users_for_referral_emails()`
- **What it does:** Finds active users eligible for referral campaign emails
- **Used for:** Weekly referral campaign emails
- **Reads from:** `User`, `Conversation`, `ReferralCode`, `UserPoints` collections

#### `get_users_with_recent_points_awards(hours=24)`
- **What it does:** Finds users who received points in the last 24 hours
- **Used for:** Points notification emails
- **Reads from:** `UserPoints` collection (points_history)

**Important:** All methods are **read-only** - they never write to the database.

---

### 2. Email Service Extensions (`app/services/email_service.py`)

**Purpose:** Email sending methods with personalized content and HTML templates.

**New Email Methods Added:**

#### `send_welcome_email(to_email, fullname)`
- **When:** 1 hour after user registration
- **Content:** Personalized welcome message with getting started tips
- **Features:** Includes call-to-action button to platform

#### `send_re_engagement_email(to_email, fullname, days_inactive)`
- **When:** Daily, for users inactive 3+ days
- **Content:** Friendly reminder, highlights new features
- **Features:** Encourages return with call-to-action

#### `send_engagement_form_email(to_email, fullname, total_chats)`
- **When:** Daily, for active users (5+ chats) without engagement info
- **Content:** Asks about use case, profession, interests
- **Features:** Includes link to engagement form

#### `send_curated_email(to_email, fullname, engagement_data)`
- **When:** Daily, for users who provided engagement info
- **Content:** Personalized tips based on:
  - User's profession
  - Use case
  - Interests
- **Features:** AI-generated or curated content relevant to user

#### `send_referral_campaign_email(to_email, fullname, referral_code, referral_link, points_balance, referral_count)`
- **When:** Weekly, for active users
- **Content:** 
  - Highlights referral program
  - Shows current points balance
  - Shows referral code and link
  - Emphasizes rewards (custom voices)
- **Features:** Creates excitement about earning points

#### `send_points_notification_email(to_email, fullname, points_awarded, reason)`
- **When:** Daily, for users who received points in last 24 hours
- **Content:** 
  - Congratulations message
  - Points earned amount
  - Reason (e.g., "A friend you referred reached 5+ chats")
  - Next steps (redeem for rewards)
- **Features:** Motivates continued engagement

**All emails use:**
- HTML templates with responsive design
- Personalized greetings (uses user's name)
- Call-to-action buttons
- Branded styling

---

### 3. Celery Tasks (`app/celery_tasks.py`)

**Purpose:** Background tasks that run on schedule to send emails automatically.

**New Tasks Added:**

#### `send_welcome_emails_task()`
- **Schedule:** Every hour
- **Process:**
  1. Calls `engagement_reader_service.get_new_users(hours_ago=1)`
  2. For each user, sends welcome email
  3. Returns statistics (sent count, failed count)

#### `send_re_engagement_emails_task()`
- **Schedule:** Daily
- **Process:**
  1. Calls `engagement_reader_service.get_inactive_users()`
  2. For each inactive user, sends re-engagement email
  3. Returns statistics

#### `send_engagement_form_emails_task()`
- **Schedule:** Daily
- **Process:**
  1. Calls `engagement_reader_service.get_active_users_for_engagement()`
  2. For each eligible user, sends engagement form email
  3. Returns statistics

#### `send_curated_emails_task()`
- **Schedule:** Daily
- **Process:**
  1. Calls `engagement_reader_service.get_users_for_curated_emails()`
  2. For each user, generates personalized curated email
  3. Uses engagement data (profession, use_case, interests) for personalization
  4. Returns statistics

#### `send_referral_campaign_emails_task()`
- **Schedule:** Weekly
- **Process:**
  1. Calls `engagement_reader_service.get_users_for_referral_emails()`
  2. For each user, sends referral campaign email with:
     - Their referral code and link
     - Current points balance
     - Referral statistics
  3. Returns statistics

#### `send_points_notification_emails_task()`
- **Schedule:** Daily
- **Process:**
  1. Calls `engagement_reader_service.get_users_with_recent_points_awards(hours=24)`
  2. For each user, sends points notification email
  3. Shows points earned and reason
  4. Returns statistics

**All tasks:**
- Are I/O-bound (use `@io_bound_task` decorator)
- Have retry logic (auto-retry on failure)
- Log success/failure statistics
- Never write to database (read-only)

---

### 4. Celery Beat Scheduler Configuration (`app/celery_app.py`)

**Purpose:** Configures when each email task runs automatically.

**Scheduled Tasks:**

```python
beat_schedule = {
    "send-welcome-emails": {
        "task": "app.celery_tasks.send_welcome_emails_task",
        "schedule": 3600.0,  # Every hour
    },
    "send-re-engagement-emails": {
        "task": "app.celery_tasks.send_re_engagement_emails_task",
        "schedule": 86400.0,  # Every day
    },
    "send-engagement-form-emails": {
        "task": "app.celery_tasks.send_engagement_form_emails_task",
        "schedule": 86400.0,  # Every day
    },
    "send-curated-emails": {
        "task": "app.celery_tasks.send_curated_emails_task",
        "schedule": 86400.0,  # Every day
    },
    "send-referral-campaign-emails": {
        "task": "app.celery_tasks.send_referral_campaign_emails_task",
        "schedule": 604800.0,  # Every week (7 days)
    },
    "send-points-notification-emails": {
        "task": "app.celery_tasks.send_points_notification_emails_task",
        "schedule": 86400.0,  # Every day
    },
}
```

**Task Routing:**
All email tasks are routed to the `io_bound` queue for optimal performance.

---

## How Integration Works

### Shared Database Architecture

Both branches share the same MongoDB database:

```
┌─────────────────────────────────────────┐
│         MongoDB Database                │
│  (Shared by both branches)              │
├─────────────────────────────────────────┤
│  • User                                 │
│  • Conversation                         │
│  • UserEngagement  (fastapi-migration)  │
│  • ReferralCode     (fastapi-migration) │
│  • Referral         (fastapi-migration)  │
│  • UserPoints       (fastapi-migration) │
└─────────────────────────────────────────┘
         ▲                    ▲
         │                    │
         │                    │
    ┌────┴────┐          ┌────┴────┐
    │  READ   │          │  WRITE  │
    │  ONLY   │          │         │
    └─────────┘          └─────────┘
feature/email-service  fastapi-migration
```

### Complete Flow Examples

#### Flow 1: Welcome Email Flow

```
1. User registers on fastapi-migration
   └─> User document created in MongoDB

2. 1 hour later, Celery task runs on feature/email-service
   └─> engagement_reader_service.get_new_users(hours_ago=1)
       └─> Reads User collection (created_at)
       └─> Finds user registered 1 hour ago
   └─> email_service.send_welcome_email()
       └─> Sends personalized welcome email
```

#### Flow 2: Engagement Form Flow

```
1. User has 5+ chats (tracked in Conversation collection)

2. Daily Celery task runs on feature/email-service
   └─> engagement_reader_service.get_active_users_for_engagement()
       └─> Reads Conversation (counts chats)
       └─> Reads UserEngagement (checks if info exists)
       └─> Finds user with 5+ chats, no engagement info
   └─> email_service.send_engagement_form_email()
       └─> Sends email with form link

3. User clicks link, fills form on fastapi-migration
   └─> POST /engagement/submit-info
       └─> engagement_service.save_user_engagement_data()
           └─> Writes to UserEngagement collection

4. Next day, Celery task runs
   └─> engagement_reader_service.get_users_for_curated_emails()
       └─> Reads UserEngagement (finds user with info)
   └─> email_service.send_curated_email()
       └─> Sends personalized tips based on profession/use_case
```

#### Flow 3: Referral & Points Flow

```
1. User A gets referral code on fastapi-migration
   └─> referral_service.generate_referral_code()
       └─> Writes ReferralCode to MongoDB

2. Weekly Celery task runs on feature/email-service
   └─> engagement_reader_service.get_users_for_referral_emails()
       └─> Reads ReferralCode (gets user's code)
       └─> Reads UserPoints (gets points balance)
       └─> Reads Referral (gets referral count)
   └─> email_service.send_referral_campaign_email()
       └─> Sends email with referral link and points info

3. User A shares link, User B signs up on fastapi-migration
   └─> referral_service.track_referral()
       └─> Writes Referral to MongoDB

4. User B has 5+ chats

5. Daily Celery task runs on fastapi-migration
   └─> check_referral_milestones_task()
       └─> Reads Conversation (checks User B's chats)
       └─> Reads Referral (finds referral relationship)
       └─> referral_service.award_referral_points()
           └─> Writes to UserPoints (adds 100 points)

6. Next day, Celery task runs on feature/email-service
   └─> engagement_reader_service.get_users_with_recent_points_awards()
       └─> Reads UserPoints (finds recent points awards)
   └─> email_service.send_points_notification_email()
       └─> Sends "You earned 100 points!" email to User A
```

---

## Key Integration Points

### 1. Data Reading (feature/email-service)

The email branch reads:
- **User data** → For personalization (name, email)
- **Conversation data** → To determine activity levels
- **UserEngagement data** → To personalize curated emails
- **ReferralCode data** → To include in referral emails
- **UserPoints data** → To show points balance and recent awards
- **Referral data** → To show referral statistics

### 2. Data Writing (fastapi-migration)

The fastapi-migration branch writes:
- **UserEngagement** → When users submit forms
- **ReferralCode** → When codes are generated
- **Referral** → When referrals are tracked
- **UserPoints** → When points are awarded/redeemed

### 3. Email Triggering

Emails are triggered by:
- **Scheduled Celery tasks** → Automatic periodic emails
- **Database state changes** → Tasks read database state and react

---

## What Makes This Integration Complete

### ✅ Separation of Concerns

- **feature/email-service**: Email infrastructure only (sending, templates, scheduling)
- **fastapi-migration**: Business logic only (data writes, API endpoints, user actions)

### ✅ Shared Database

- Both branches read/write to the same MongoDB
- No direct communication needed between branches
- Database acts as the integration layer

### ✅ Complete User Journey

1. **Registration** → Welcome email (1 hour delay)
2. **Inactivity** → Re-engagement email (3+ days)
3. **Active Usage** → Engagement form email (5+ chats)
4. **Info Provided** → Curated emails (daily personalized tips)
5. **Referral Sharing** → Campaign emails (weekly)
6. **Points Earned** → Notification emails (when awarded)

### ✅ Automated System

- All emails sent automatically via Celery Beat scheduler
- No manual intervention needed
- Scales with user base

### ✅ Personalization

- Uses user's name in greetings
- Uses engagement data for curated content
- Shows relevant information (points, referral stats)
- Tailored to user's activity level

---

## Configuration

### Environment Variables

Both branches use these (shared via .env):

```bash
# Email Configuration
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
FRONTEND_URL=https://artemis.ares.codes
APP_NAME=Artemis - AI Assistant

# Engagement Configuration
ENGAGEMENT_ENABLED=true
RE_ENGAGEMENT_THRESHOLD_DAYS=3
MIN_CHATS_FOR_ENGAGEMENT=5

# Referral Configuration
POINTS_PER_REFERRAL=100
CUSTOM_VOICE_POINTS_COST=500  # (Note: Now uses grade-based pricing)
```

---

## Testing the Integration

### Manual Testing Steps

1. **Test Welcome Email:**
   - Register a new user on fastapi-migration
   - Wait 1 hour
   - Check email inbox for welcome email

2. **Test Re-engagement Email:**
   - Create a user with last activity 4 days ago
   - Run `send_re_engagement_emails_task` manually
   - Check email inbox

3. **Test Engagement Form Email:**
   - Create user with 5+ conversations, no engagement data
   - Run `send_engagement_form_emails_task` manually
   - Check email inbox

4. **Test Referral Flow:**
   - User A gets referral code
   - User B signs up with referral code
   - User B has 5+ chats
   - Check User A's points (should be +100)
   - Check User A's email for points notification

---

## Summary

The `feature/email-service` branch completes the integration by:

1. ✅ **Reading database state** to identify users for different email types
2. ✅ **Sending personalized emails** with HTML templates
3. ✅ **Automating email delivery** via Celery Beat scheduler
4. ✅ **Reacting to data changes** by reading updated database state
5. ✅ **Maintaining read-only operations** (no database writes)

Together with `fastapi-migration` (which handles writes and business logic), this creates a complete, automated email engagement and referral system that:
- Engages users at the right time
- Personalizes content based on user data
- Rewards referrals automatically
- Scales with the user base
- Requires no manual intervention

The system is **production-ready** and **fully automated**.

