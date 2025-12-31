# Engagement & Referral System API Documentation

## Overview

This document describes the Engagement and Referral System API endpoints implemented on the `fastapi-migration` branch. This system enables:

1. **User Engagement Tracking**: Collect user information through forms to personalize their experience
2. **Referral System**: Allow users to refer friends and earn points when referrals become active
3. **Points & Rewards**: Users can earn points through referrals and redeem them for TTS voices based on quality grades

## Table of Contents

- [Engagement Endpoints](#engagement-endpoints)
- [Referral Endpoints](#referral-endpoints)
- [Data Models](#data-models)
- [Workflow Examples](#workflow-examples)
- [Points & Rewards System](#points--rewards-system)

---

## Engagement Endpoints

### 1. Submit Engagement Information

**Endpoint:** `POST /engagement/submit-info`

**Description:** Submit user engagement information collected from forms (use case, profession, interests, goals).

**Authentication:** Required (JWT token)

**Request Body:**
```json
{
  "use_case": "How I use Artemis in my daily work",
  "profession": "Software Engineer",
  "interests": ["AI", "Technology", "Productivity"],
  "goals": "I want to automate my workflow and get better at using AI tools"
}
```

**Request Model:**
- `use_case` (string, optional, max 500 chars): How the user uses Artemis
- `profession` (string, optional, max 200 chars): What the user does for a living
- `interests` (array of strings, optional): Areas of interest
- `goals` (string, optional, max 1000 chars): What the user wants to achieve

**Response:**
```json
{
  "success": true,
  "message": "Engagement information saved successfully",
  "data": {
    "user_id": "507f1f77bcf86cd799439011",
    "use_case": "How I use Artemis in my daily work",
    "profession": "Software Engineer",
    "interests": ["AI", "Technology", "Productivity"],
    "goals": "I want to automate my workflow...",
    "info_collected": true,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid input data
- `401 Unauthorized`: Missing or invalid JWT token
- `500 Internal Server Error`: Server error

---

### 2. Get Email Preferences

**Endpoint:** `GET /engagement/preferences`

**Description:** Get current user's email preferences (opt-in status and frequency).

**Authentication:** Required (JWT token)

**Response:**
```json
{
  "success": true,
  "data": {
    "email_opt_in": true,
    "email_frequency": "daily"
  }
}
```

**Email Frequency Options:**
- `daily`: Receive emails daily
- `weekly`: Receive emails weekly
- `biweekly`: Receive emails bi-weekly
- `monthly`: Receive emails monthly

---

### 3. Update Email Preferences

**Endpoint:** `PUT /engagement/preferences`

**Description:** Update user's email preferences.

**Authentication:** Required (JWT token)

**Request Body:**
```json
{
  "email_opt_in": true,
  "email_frequency": "weekly"
}
```

**Request Model:**
- `email_opt_in` (boolean, optional): Whether to receive emails
- `email_frequency` (string, optional): Email frequency (`daily`, `weekly`, `biweekly`, `monthly`)

**Response:**
```json
{
  "success": true,
  "message": "Email preferences updated successfully",
  "data": {
    "user_id": "507f1f77bcf86cd799439011",
    "email_opt_in": true,
    "email_frequency": "weekly"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid frequency value
- `401 Unauthorized`: Missing or invalid JWT token
- `500 Internal Server Error`: Server error

---

### 4. Get Engagement Statistics

**Endpoint:** `GET /engagement/stats`

**Description:** Get user's engagement statistics and collected information.

**Authentication:** Required (JWT token)

**Response:**
```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "has_engagement_data": true,
  "info_collected": true,
  "use_case": "How I use Artemis in my daily work",
  "profession": "Software Engineer",
  "interests": ["AI", "Technology", "Productivity"],
  "goals": "I want to automate my workflow...",
  "email_opt_in": true,
  "email_frequency": "daily",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

## Referral Endpoints

### 1. Get Referral Code

**Endpoint:** `GET /referral/code`

**Description:** Get user's unique referral code and referral link. Creates a code if one doesn't exist.

**Authentication:** Required (JWT token)

**Response:**
```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "referral_code": "ARTEMIS-ABC123",
  "referral_link": "https://artemis.ares.codes/signup?ref=ARTEMIS-ABC123"
}
```

**Response Model:**
- `user_id` (string): User's unique ID
- `referral_code` (string): Unique referral code (format: `ARTEMIS-XXXXXX`)
- `referral_link` (string): Full referral URL with code

---

### 2. Register Referral

**Endpoint:** `POST /referral/register`

**Description:** Register a referral when a new user signs up with a referral code. This is typically called during the registration process.

**Authentication:** Required (JWT token)

**Request Body:**
```json
{
  "referral_code": "ARTEMIS-ABC123"
}
```

**Request Model:**
- `referral_code` (string, required): The referral code used during signup

**Response:**
```json
{
  "success": true,
  "message": "Referral registered successfully",
  "data": {
    "referrer_id": "507f1f77bcf86cd799439012",
    "referred_user_id": "507f1f77bcf86cd799439011",
    "referral_code": "ARTEMIS-ABC123",
    "engagement_milestones": [],
    "points_awarded": false,
    "points_amount": 0,
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid or inactive referral code
- `401 Unauthorized`: Missing or invalid JWT token
- `500 Internal Server Error`: Server error

**Note:** This endpoint is also automatically called during user registration (both regular and OAuth) if a referral code is provided in the signup URL.

---

### 3. Get Referral Statistics

**Endpoint:** `GET /referral/stats`

**Description:** Get user's referral statistics including total referrals, successful referrals, and points earned.

**Authentication:** Required (JWT token)

**Response:**
```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "referral_code": "ARTEMIS-ABC123",
  "total_referrals": 5,
  "successful_referrals": 3,
  "total_points": 300,
  "points_from_referrals": 300
}
```

**Response Model:**
- `user_id` (string): User's unique ID
- `referral_code` (string, nullable): User's referral code
- `total_referrals` (integer): Total number of users referred
- `successful_referrals` (integer): Number of referrals that reached 5+ chats (points awarded)
- `total_points` (integer): Current total points balance
- `points_from_referrals` (integer): Total points earned from referrals

---

### 4. Get Points Balance

**Endpoint:** `GET /referral/points`

**Description:** Get user's current points balance and redemption history.

**Authentication:** Required (JWT token)

**Response:**
```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "total_points": 500,
  "rewards_redeemed": ["voice:af_heart", "voice:af_bella"],
  "points_history_count": 5
}
```

**Response Model:**
- `user_id` (string): User's unique ID
- `total_points` (integer): Current points balance
- `rewards_redeemed` (array of strings): List of redeemed rewards (format: `voice:voice_name`)
- `points_history_count` (integer): Number of points history entries

---

### 5. Redeem Points

**Endpoint:** `POST /referral/redeem`

**Description:** Redeem points for rewards (currently supports TTS voices).

**Authentication:** Required (JWT token)

**Request Body:**
```json
{
  "reward_type": "voice",
  "voice_name": "af_heart"
}
```

**Request Model:**
- `reward_type` (string, required): Type of reward to redeem (currently only `"voice"`)
- `voice_name` (string, optional): Voice name if redeeming a voice (e.g., `"af_heart"`)

**Response:**
```json
{
  "success": true,
  "message": "Successfully redeemed voice",
  "data": {
    "user_id": "507f1f77bcf86cd799439011",
    "reward_type": "voice",
    "voice_name": "af_heart",
    "grade": "A",
    "points_spent": 1000,
    "remaining_points": 0,
    "rewards_redeemed": ["voice:af_heart"]
  }
}
```

**Error Responses:**
- `400 Bad Request`: 
  - Insufficient points
  - Unknown voice or reward type
  - Voice already redeemed
- `401 Unauthorized`: Missing or invalid JWT token
- `500 Internal Server Error`: Server error

**Note:** When a voice is redeemed, it is automatically set as the user's TTS voice preference.

---

### 6. Get Available Rewards

**Endpoint:** `GET /referral/rewards`

**Description:** Get all available rewards (TTS voices) with their point costs, organized by grade.

**Authentication:** Required (JWT token)

**Response:**
```json
{
  "rewards": [
    {
      "type": "voice",
      "voice_name": "af_heart",
      "name": "American Female - Heart (❤️)",
      "description": "Grade A TTS Voice",
      "grade": "A",
      "points_cost": 1000,
      "available": false,
      "redeemed": false
    },
    {
      "type": "voice",
      "voice_name": "af_bella",
      "name": "American Female - Bella (🔥)",
      "description": "Grade A- TTS Voice",
      "grade": "A-",
      "points_cost": 800,
      "available": false,
      "redeemed": false
    },
    {
      "type": "voice",
      "voice_name": "af_nicole",
      "name": "American Female - Nicole (🎧)",
      "description": "Grade B- TTS Voice",
      "grade": "B-",
      "points_cost": 600,
      "available": true,
      "redeemed": false
    }
  ],
  "points_balance": 500
}
```

**Response Model:**
- `rewards` (array): List of available voice rewards, sorted by grade (A to F)
  - `type` (string): Always `"voice"` for voice rewards
  - `voice_name` (string): Voice identifier (e.g., `"af_heart"`)
  - `name` (string): Human-readable voice name
  - `description` (string): Voice description with grade
  - `grade` (string): Voice quality grade (A, A-, B-, C+, C, C-, D+, D, D-, F+)
  - `points_cost` (integer): Points required to redeem
  - `available` (boolean): Whether user has enough points to redeem
  - `redeemed` (boolean): Whether user has already redeemed this voice
- `points_balance` (integer): User's current points balance

**Voice Grade Point Costs:**
- **Grade A**: 1000 points (Premium quality)
- **Grade A-**: 800 points (High quality)
- **Grade B-**: 600 points (Good quality)
- **Grade C+**: 400 points (Standard quality)
- **Grade C**: 300 points (Basic quality)
- **Grade C-**: 250 points (Basic- quality)
- **Grade D+**: 200 points (Low quality)
- **Grade D**: 150 points (Low quality)
- **Grade D-**: 100 points (Very low quality)
- **Grade F+**: 50 points (Lowest quality)

---

## Data Models

### UserEngagement

Stores user engagement data and email preferences.

```python
{
  "user_id": "string (unique)",
  "use_case": "string (max 500)",
  "profession": "string (max 200)",
  "interests": ["string"],
  "goals": "string (max 1000)",
  "email_opt_in": boolean,
  "email_frequency": "daily|weekly|biweekly|monthly",
  "info_collected": boolean,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### ReferralCode

Stores unique referral codes for each user.

```python
{
  "user_id": "string (unique)",
  "code": "string (unique, format: ARTEMIS-XXXXXX)",
  "is_active": boolean,
  "usage_count": integer,
  "created_at": "datetime"
}
```

### Referral

Tracks referral relationships and milestones.

```python
{
  "referrer_id": "string",
  "referred_user_id": "string (unique)",
  "referral_code": "string",
  "engagement_milestones": ["string"],
  "points_awarded": boolean,
  "points_awarded_at": "datetime (nullable)",
  "points_amount": integer,
  "created_at": "datetime"
}
```

### UserPoints

Stores user's points balance and redemption history.

```python
{
  "user_id": "string (unique)",
  "total_points": integer,
  "points_history": [
    {
      "amount": integer,
      "type": "earned|spent|redeemed",
      "source": "string",
      "description": "string",
      "timestamp": "datetime"
    }
  ],
  "rewards_redeemed": ["string"],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

## Workflow Examples

### Example 1: Complete Referral Flow

1. **User A gets referral code:**
   ```bash
   GET /referral/code
   # Returns: { "referral_code": "ARTEMIS-ABC123", "referral_link": "..." }
   ```

2. **User A shares link with User B:**
   - Link: `https://artemis.ares.codes/signup?ref=ARTEMIS-ABC123`

3. **User B signs up:**
   - Registration automatically tracks referral
   - Referral relationship created

4. **User B has 5+ conversations:**
   - Daily Celery task checks milestones
   - Points automatically awarded to User A (100 points)
   - User A receives notification email

5. **User A redeems voice:**
   ```bash
   POST /referral/redeem
   {
     "reward_type": "voice",
     "voice_name": "af_nicole"
   }
   # Costs 600 points (Grade B-)
   ```

### Example 2: Engagement Data Collection

1. **User submits engagement form:**
   ```bash
   POST /engagement/submit-info
   {
     "use_case": "I use Artemis for coding assistance",
     "profession": "Software Developer",
     "interests": ["Programming", "AI"],
     "goals": "Improve productivity"
   }
   ```

2. **System uses this data:**
   - Personalized curated emails sent daily
   - Content tailored to profession and interests
   - Tips relevant to use case

3. **User updates preferences:**
   ```bash
   PUT /engagement/preferences
   {
     "email_frequency": "weekly"
   }
   ```

---

## Points & Rewards System

### Earning Points

- **100 points** when a referred user completes 5+ chats
- Points are automatically awarded via daily Celery task
- Points are tracked in `UserPoints` with full history

### Redeeming Points

Users can redeem points for TTS voices based on quality grades:

- **Premium Voices (Grade A)**: 1000 points
  - `af_heart` - American Female - Heart (❤️)

- **High Quality Voices (Grade A-)**: 800 points
  - `af_bella` - American Female - Bella (🔥)

- **Good Quality Voices (Grade B-)**: 600 points
  - `af_nicole` - American Female - Nicole (🎧)
  - `bf_emma` - British Female - Emma

- **Standard Voices (Grade C+)**: 400 points
  - `af_aoede`, `af_kore`, `af_sarah`, `am_fenrir`, `am_michael`, `am_puck`

- **Basic Voices (Grade C)**: 300 points
  - `af_alloy`, `af_nova`, `bf_isabella`, `bm_fable`, `bm_george`

- **Basic- Voices (Grade C-)**: 250 points
  - `af_sky`

- **Low Quality Voices (Grade D+)**: 200 points
  - `bm_lewis`

- **Low Quality Voices (Grade D)**: 150 points
  - `af_jessica`, `af_river`, `am_echo`, `am_eric`, `am_liam`, `am_onyx`, `am_santa`, `bf_alice`, `bf_lily`, `bm_daniel`

- **Very Low Quality Voices (Grade D-)**: 100 points
  - `am_santa`

- **Lowest Quality Voices (Grade F+)**: 50 points
  - `am_adam`

### Voice Redemption Process

1. User checks available rewards: `GET /referral/rewards`
2. User selects a voice they can afford
3. User redeems: `POST /referral/redeem` with `voice_name`
4. Points are deducted from balance
5. Voice is automatically set as user's TTS preference
6. Voice is marked as redeemed (cannot redeem again)

---

## Integration with Registration

### Regular Registration

When a user signs up with a referral code in the URL (`?ref=ARTEMIS-ABC123`), the referral is automatically tracked during registration.

### OAuth Registration

When a user signs up via Google OAuth with a referral code, the referral is tracked in the OAuth callback.

**OAuth Callback URL:**
```
GET /auth/google/callback?code=...&ref=ARTEMIS-ABC123
```

The `ref` parameter is automatically extracted and used to track the referral.

---

## Automated Processes

### Daily Celery Tasks

1. **Check Referral Milestones** (`check_referral_milestones_task`)
   - Runs daily
   - Checks if referred users reached 5+ chats
   - Awards 100 points to referrers automatically
   - Marks referrals as points awarded

2. **Points Notification Emails** (on `feature/email-service` branch)
   - Sends email when points are awarded
   - Shows points earned and reason

---

## Error Handling

All endpoints return appropriate HTTP status codes:

- **200 OK**: Successful request
- **400 Bad Request**: Invalid input, insufficient points, or business logic error
- **401 Unauthorized**: Missing or invalid JWT token
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Server error

Error responses include a `detail` field with a descriptive error message:

```json
{
  "detail": "Insufficient points. Balance: 100, Required: 600 (Grade B- voice)"
}
```

---

## Authentication

All endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

Tokens are obtained through the authentication endpoints (`/auth/login` or `/auth/google/callback`).

---

## Rate Limiting

Currently, no rate limiting is implemented. Consider adding rate limiting for production use.

---

## Database Indexes

The following indexes are created for optimal performance:

- `UserEngagement`: `user_id` (unique)
- `ReferralCode`: `user_id` (unique), `code` (unique)
- `Referral`: `referrer_id`, `referred_user_id` (unique), `referral_code`
- `UserPoints`: `user_id` (unique), `total_points`

---

## Future Enhancements

Potential future additions:

1. Additional reward types (premium features, API credits, etc.)
2. Bonus point campaigns
3. Referral leaderboards
4. Multi-tier referral bonuses
5. Points expiration system
6. Gift points to other users

---

## Support

For issues or questions, please contact the development team or refer to the main project documentation.

