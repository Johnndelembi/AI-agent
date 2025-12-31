# Admin Dashboard API Documentation

## Overview

The Admin Dashboard provides comprehensive endpoints for administrators to manage users, track email sends, monitor referrals, and view activity metrics. All endpoints require admin privileges.

**Base Path**: `/admin`

**Authentication**: All endpoints require a valid JWT token with admin privileges. Use the `Authorization: Bearer <token>` header.

---

## Table of Contents

1. [User Management](#user-management)
2. [Email Tracking](#email-tracking)
3. [Referral Management](#referral-management)
4. [Activity Metrics](#activity-metrics)
5. [Dashboard Statistics](#dashboard-statistics)
6. [Response Models](#response-models)
7. [Error Handling](#error-handling)

---

## User Management

### List All Users

Get a paginated list of all users with optional filters.

**Endpoint**: `GET /admin/users`

**Query Parameters**:
- `page` (int, default: 1): Page number (1-indexed)
- `page_size` (int, default: 50, max: 100): Items per page
- `is_active` (bool, optional): Filter by active status
- `is_verified` (bool, optional): Filter by verified status
- `is_admin` (bool, optional): Filter by admin status
- `search` (string, optional): Search by email or name
- `start_date` (string, optional): Filter users created after this date (ISO format)
- `end_date` (string, optional): Filter users created before this date (ISO format)

**Example Request**:
```bash
GET /admin/users?page=1&page_size=50&is_active=true&search=john
Authorization: Bearer <admin_token>
```

**Example Response**:
```json
{
  "users": [
    {
      "id": "507f1f77bcf86cd799439011",
      "email": "user@example.com",
      "fullname": "John Doe",
      "is_active": true,
      "is_verified": true,
      "is_admin": false,
      "created_at": "2025-01-15T10:30:00Z",
      "last_login": "2025-01-20T14:22:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50,
  "total_pages": 3
}
```

---

### Get User Details

Get complete information about a specific user including engagement data, points, referrals, and activity.

**Endpoint**: `GET /admin/users/{user_id}`

**Path Parameters**:
- `user_id` (string): User ID

**Example Request**:
```bash
GET /admin/users/507f1f77bcf86cd799439011
Authorization: Bearer <admin_token>
```

**Example Response**:
```json
{
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "email": "user@example.com",
    "fullname": "John Doe",
    "is_active": true,
    "is_verified": true,
    "created_at": "2025-01-15T10:30:00Z"
  },
  "engagement": {
    "user_id": "507f1f77bcf86cd799439011",
    "profession": "Software Engineer",
    "use_case": "Code assistance",
    "interests": ["programming", "ai"],
    "email_opt_in": true,
    "email_frequency": "daily"
  },
  "points": {
    "user_id": "507f1f77bcf86cd799439011",
    "total_points": 250,
    "rewards_redeemed": ["voice:af_heart"],
    "points_history_count": 5
  },
  "referral_code": {
    "user_id": "507f1f77bcf86cd799439011",
    "code": "ARTEMIS-ABC123",
    "usage_count": 3
  },
  "referrals_made": [
    {
      "referrer_id": "507f1f77bcf86cd799439011",
      "referred_user_id": "507f1f77bcf86cd799439012",
      "points_awarded": true,
      "points_amount": 100
    }
  ],
  "referral_received": null,
  "conversation_count": 42,
  "email_count": 15
}
```

---

## Email Tracking

### List Email Logs

Get paginated list of email logs with optional filters.

**Endpoint**: `GET /admin/emails`

**Query Parameters**:
- `user_id` (string, optional): Filter by user ID
- `email_type` (string, optional): Filter by email type (welcome, re_engagement, curated, referral_campaign, points_notification, engagement_form)
- `start_date` (string, optional): Filter emails sent after this date (ISO format)
- `end_date` (string, optional): Filter emails sent before this date (ISO format)
- `page` (int, default: 1): Page number
- `page_size` (int, default: 100, max: 500): Items per page

**Example Request**:
```bash
GET /admin/emails?email_type=welcome&start_date=2025-01-01T00:00:00Z&page=1
Authorization: Bearer <admin_token>
```

**Example Response**:
```json
{
  "logs": [
    {
      "id": "507f1f77bcf86cd799439020",
      "user_id": "507f1f77bcf86cd799439011",
      "email_type": "welcome",
      "recipient_email": "user@example.com",
      "subject": "Welcome to Artemis - AI Assistant!",
      "sent_at": "2025-01-15T10:35:00Z",
      "status": "sent",
      "metadata": {
        "fullname": "John Doe"
      }
    }
  ],
  "total": 1250,
  "page": 1,
  "page_size": 100,
  "total_pages": 13
}
```

---

### Get User Email History

Get email history for a specific user.

**Endpoint**: `GET /admin/emails/user/{user_id}`

**Path Parameters**:
- `user_id` (string): User ID

**Query Parameters**:
- `email_type` (string, optional): Filter by email type
- `limit` (int, default: 100, max: 500): Maximum number of results

**Example Request**:
```bash
GET /admin/emails/user/507f1f77bcf86cd799439011?email_type=curated&limit=50
Authorization: Bearer <admin_token>
```

**Example Response**:
```json
[
  {
    "id": "507f1f77bcf86cd799439020",
    "user_id": "507f1f77bcf86cd799439011",
    "email_type": "curated",
    "recipient_email": "user@example.com",
    "subject": "Your Daily Artemis Tip",
    "sent_at": "2025-01-20T08:00:00Z",
    "status": "sent",
    "metadata": {}
  }
]
```

---

## Referral Management

### Get Referral Statistics

Get aggregate referral statistics including top referrers.

**Endpoint**: `GET /admin/referrals`

**Example Request**:
```bash
GET /admin/referrals
Authorization: Bearer <admin_token>
```

**Example Response**:
```json
{
  "total_referrals": 450,
  "successful_referrals": 320,
  "total_points_awarded": 32000,
  "top_referrers": [
    {
      "user_id": "507f1f77bcf86cd799439011",
      "email": "user@example.com",
      "fullname": "John Doe",
      "referral_count": 15,
      "total_points": 1500
    }
  ]
}
```

---

### Get User Referrals

Get referrals made by a specific user.

**Endpoint**: `GET /admin/referrals/user/{user_id}`

**Path Parameters**:
- `user_id` (string): User ID (referrer)

**Example Request**:
```bash
GET /admin/referrals/user/507f1f77bcf86cd799439011
Authorization: Bearer <admin_token>
```

**Example Response**:
```json
{
  "referral_code": {
    "user_id": "507f1f77bcf86cd799439011",
    "code": "ARTEMIS-ABC123",
    "usage_count": 5
  },
  "total_referrals": 5,
  "successful_referrals": 3,
  "referrals": [
    {
      "referrer_id": "507f1f77bcf86cd799439011",
      "referred_user_id": "507f1f77bcf86cd799439012",
      "referral_code": "ARTEMIS-ABC123",
      "points_awarded": true,
      "points_amount": 100,
      "referred_user": {
        "id": "507f1f77bcf86cd799439012",
        "email": "referred@example.com",
        "fullname": "Jane Smith"
      }
    }
  ]
}
```

---

## Activity Metrics

### Get User Activity Metrics

Get activity metrics for a specific user including login history, conversation counts, and email activity.

**Endpoint**: `GET /admin/activity/{user_id}`

**Path Parameters**:
- `user_id` (string): User ID

**Example Request**:
```bash
GET /admin/activity/507f1f77bcf86cd799439011
Authorization: Bearer <admin_token>
```

**Example Response**:
```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "last_login": "2025-01-20T14:22:00Z",
  "days_since_login": 2,
  "account_created_at": "2025-01-15T10:30:00Z",
  "days_since_creation": 5,
  "conversation_count": 42,
  "total_messages": 156,
  "email_count": 15,
  "last_email_sent": {
    "id": "507f1f77bcf86cd799439020",
    "email_type": "curated",
    "subject": "Your Daily Artemis Tip",
    "sent_at": "2025-01-20T08:00:00Z"
  }
}
```

---

## Dashboard Statistics

### Get Dashboard Overview

Get comprehensive dashboard statistics including user counts, email statistics, referral metrics, and conversation data.

**Endpoint**: `GET /admin/dashboard/stats`

**Example Request**:
```bash
GET /admin/dashboard/stats
Authorization: Bearer <admin_token>
```

**Example Response**:
```json
{
  "users": {
    "total": 1250,
    "active": 1100,
    "verified": 1200,
    "admins": 5,
    "new_7d": 45,
    "new_30d": 180,
    "active_7d": 850
  },
  "emails": {
    "total": 8500,
    "sent_7d": 320,
    "sent_30d": 1450,
    "by_type": {
      "welcome": 1200,
      "re_engagement": 450,
      "curated": 2800,
      "referral_campaign": 320,
      "points_notification": 180,
      "engagement_form": 150
    }
  },
  "referrals": {
    "total": 450,
    "successful": 320
  },
  "conversations": {
    "total": 12500,
    "total_messages": 45000
  }
}
```

---

## Response Models

### UserListResponse
```typescript
{
  users: User[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
```

### UserDetailResponse
```typescript
{
  user: User;
  engagement?: UserEngagement;
  points?: UserPoints;
  referral_code?: ReferralCode;
  referrals_made: Referral[];
  referral_received?: Referral;
  conversation_count: number;
  email_count: number;
}
```

### EmailLogResponse
```typescript
{
  id: string;
  user_id: string;
  email_type: string;
  recipient_email: string;
  subject: string;
  sent_at: string;
  status: "sent" | "failed";
  metadata: Record<string, any>;
}
```

### ReferralStatsResponse
```typescript
{
  total_referrals: number;
  successful_referrals: number;
  total_points_awarded: number;
  top_referrers: TopReferrer[];
}
```

### UserActivityResponse
```typescript
{
  user_id: string;
  last_login?: string;
  days_since_login?: number;
  account_created_at?: string;
  days_since_creation?: number;
  conversation_count: number;
  total_messages: number;
  email_count: number;
  last_email_sent?: EmailLog;
}
```

### DashboardStatsResponse
```typescript
{
  users: {
    total: number;
    active: number;
    verified: number;
    admins: number;
    new_7d: number;
    new_30d: number;
    active_7d: number;
  };
  emails: {
    total: number;
    sent_7d: number;
    sent_30d: number;
    by_type: Record<string, number>;
  };
  referrals: {
    total: number;
    successful: number;
  };
  conversations: {
    total: number;
    total_messages: number;
  };
}
```

---

## Error Handling

All endpoints return standard HTTP status codes:

- **200 OK**: Request successful
- **400 Bad Request**: Invalid request parameters
- **401 Unauthorized**: Missing or invalid authentication token
- **403 Forbidden**: User does not have admin privileges
- **404 Not Found**: Resource not found (e.g., user not found)
- **500 Internal Server Error**: Server error

**Error Response Format**:
```json
{
  "detail": "Error message describing what went wrong"
}
```

---

## Email Types

The following email types are tracked:

- `welcome`: Welcome email sent to new users
- `re_engagement`: Re-engagement email for inactive users
- `curated`: Curated/personalized tip emails
- `referral_campaign`: Referral campaign emails
- `points_notification`: Points earned notifications
- `engagement_form`: Engagement form request emails
- `notification`: General notification emails
- `other`: Other email types

---

## Usage Examples

### Get all active users created in the last 30 days
```bash
curl -X GET "https://api.example.com/admin/users?is_active=true&start_date=2025-01-01T00:00:00Z" \
  -H "Authorization: Bearer <admin_token>"
```

### Get email statistics for a specific user
```bash
curl -X GET "https://api.example.com/admin/emails/user/507f1f77bcf86cd799439011" \
  -H "Authorization: Bearer <admin_token>"
```

### Get dashboard overview
```bash
curl -X GET "https://api.example.com/admin/dashboard/stats" \
  -H "Authorization: Bearer <admin_token>"
```

---

## Notes

- All date parameters should be in ISO 8601 format (e.g., `2025-01-15T10:30:00Z`)
- Pagination is 1-indexed (first page is page 1)
- Maximum page sizes are enforced to prevent performance issues
- All endpoints require admin privileges - regular users will receive a 403 Forbidden response
- Email logs are automatically created when emails are sent through the EmailService

---

## Support

For issues or questions about the Admin Dashboard API, please contact the development team.

