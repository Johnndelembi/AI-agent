# Frontend Referral System Integration Guide

This document provides instructions for integrating the referral system with Google OAuth signup on the frontend.

## Overview

The referral system allows users to share referral links. When someone signs up using a referral link, the referrer earns points. The referral code is passed through the Google OAuth flow using the `state` parameter.

---

## Referral Link Format

Referral links follow this format:

```
https://artemis.ares.codes/auth/google/login?state=ARTEMIS-XXXXXX
```

Where `ARTEMIS-XXXXXX` is the unique referral code (e.g., `ARTEMIS-0XZ9DS`).

---

## How It Works

### Flow Diagram

```
1. User clicks referral link
   ↓
2. Frontend receives: /auth/google/login?state=ARTEMIS-XXXXXX
   ↓
3. Frontend redirects to backend: /api/auth/google/login?state=ARTEMIS-XXXXXX
   ↓
4. Backend redirects to Google OAuth (state preserved)
   ↓
5. User authenticates with Google
   ↓
6. Google redirects to: /api/auth/google/callback?code=...&state=ARTEMIS-XXXXXX
   ↓
7. Backend extracts referral code from state and creates user
   ↓
8. Referral is automatically tracked ✅
```

---

## Frontend Implementation

### Option 1: Direct Redirect (Recommended)

If a user visits your site with a referral link, redirect them directly to the backend OAuth endpoint:

```javascript
// Example: User visits https://artemis.ares.codes/auth/google/login?state=ARTEMIS-0XZ9DS

// Extract state parameter
const urlParams = new URLSearchParams(window.location.search);
const referralCode = urlParams.get('state'); // "ARTEMIS-0XZ9DS"

if (referralCode && referralCode.startsWith('ARTEMIS-')) {
  // Redirect to backend OAuth endpoint with state parameter
  window.location.href = `https://api.artemis.ares.codes/auth/google/login?state=${referralCode}`;
}
```

**Note:** The backend will handle the Google OAuth flow and preserve the `state` parameter through the entire process.

---

### Option 2: Frontend OAuth Handler

If your frontend handles OAuth callbacks, you need to:

1. **Capture the referral code from the URL**
2. **Pass it to your OAuth initiation**
3. **Ensure it's preserved through the flow**

```javascript
// On your signup/login page
function handleReferralSignup() {
  // Check if there's a referral code in the URL
  const urlParams = new URLSearchParams(window.location.search);
  const referralCode = urlParams.get('state') || urlParams.get('ref');
  
  if (referralCode && referralCode.startsWith('ARTEMIS-')) {
    // Initiate OAuth with referral code in state parameter
    const oauthUrl = `https://api.artemis.ares.codes/auth/google/login?state=${referralCode}`;
    window.location.href = oauthUrl;
  } else {
    // Normal OAuth without referral
    window.location.href = 'https://api.artemis.ares.codes/auth/google/login';
  }
}
```

---

### Option 3: React/Next.js Example

```jsx
// pages/signup.js or components/SignupButton.jsx
import { useRouter } from 'next/router';
import { useEffect } from 'react';

export default function SignupPage() {
  const router = useRouter();
  
  useEffect(() => {
    // Check for referral code in URL
    const referralCode = router.query.state || router.query.ref;
    
    if (referralCode && referralCode.startsWith('ARTEMIS-')) {
      // Redirect to OAuth with referral code
      window.location.href = `https://api.artemis.ares.codes/auth/google/login?state=${referralCode}`;
    }
  }, [router.query]);
  
  const handleGoogleSignup = () => {
    // Check for referral code
    const referralCode = router.query.state || router.query.ref;
    const oauthUrl = referralCode 
      ? `https://api.artemis.ares.codes/auth/google/login?state=${referralCode}`
      : 'https://api.artemis.ares.codes/auth/google/login';
    
    window.location.href = oauthUrl;
  };
  
  return (
    <div>
      <button onClick={handleGoogleSignup}>
        Sign up with Google
      </button>
    </div>
  );
}
```

---

## API Endpoints

### 1. Get User's Referral Code

**Endpoint:** `GET /api/referral/code`

**Authentication:** Required (JWT token)

**Response:**
```json
{
  "user_id": "507f1f77bcf86cd799439011",
  "referral_code": "ARTEMIS-0XZ9DS",
  "referral_link": "https://artemis.ares.codes/auth/google/login?state=ARTEMIS-0XZ9DS"
}
```

**Usage:**
```javascript
// Get user's referral code to display/share
const response = await fetch('https://api.artemis.ares.codes/referral/code', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});

const data = await response.json();
console.log('Share this link:', data.referral_link);
```

---

### 2. Google OAuth Login (with Referral)

**Endpoint:** `GET /api/auth/google/login?state=ARTEMIS-XXXXXX`

**Parameters:**
- `state` (optional): Referral code (e.g., `ARTEMIS-0XZ9DS`)

**Behavior:**
- Redirects to Google OAuth
- Preserves `state` parameter through OAuth flow
- After authentication, redirects to callback with `state` intact

**Usage:**
```javascript
// Redirect user to OAuth with referral code
const referralCode = 'ARTEMIS-0XZ9DS';
window.location.href = `https://api.artemis.ares.codes/auth/google/login?state=${referralCode}`;
```

---

### 3. Google OAuth Callback

**Endpoint:** `GET /api/auth/google/callback`

**Parameters:**
- `code`: Authorization code from Google
- `state`: Referral code (if provided)
- `redirect_uri`: (optional) Custom redirect URI

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    ...
  }
}
```

**Note:** The referral is automatically tracked when a new user is created. No additional API call is needed.

---

## Important Notes

### 1. Referral Code Format

- All referral codes start with `ARTEMIS-` followed by 6 alphanumeric characters
- Example: `ARTEMIS-0XZ9DS`, `ARTEMIS-ABC123`
- Validate referral codes before using them:
  ```javascript
  function isValidReferralCode(code) {
    return code && code.startsWith('ARTEMIS-') && code.length === 14;
  }
  ```

### 2. State Parameter Preservation

- The `state` parameter is automatically preserved by Google OAuth
- It will be returned in the callback URL
- The backend extracts it automatically - no frontend action needed

### 3. Referral Tracking

- **Automatic**: Referrals are tracked automatically when a new user signs up with a referral code
- **No extra API calls needed**: The backend handles everything
- **Points awarded later**: Points are awarded when the referred user reaches 5+ chats (handled by backend)

### 4. Existing Users

- If a user already has an account and signs in with a referral link, the referral is **not** tracked
- Referrals are only tracked for **new user registrations**

---

## Frontend Pages Needed

### 1. Signup/Login Page

**URL:** `/auth/google/login` or `/signup`

**Behavior:**
- Check for `?state=ARTEMIS-XXXXXX` in URL
- If present, redirect to backend OAuth with state parameter
- If not present, redirect to normal OAuth

**Example:**
```javascript
// Check URL for referral code
const urlParams = new URLSearchParams(window.location.search);
const referralCode = urlParams.get('state');

if (referralCode && referralCode.startsWith('ARTEMIS-')) {
  // Redirect with referral code
  window.location.href = `https://api.artemis.ares.codes/auth/google/login?state=${referralCode}`;
} else {
  // Normal signup
  window.location.href = 'https://api.artemis.ares.codes/auth/google/login';
}
```

### 2. OAuth Callback Page (Optional)

**URL:** `/auth/google/callback`

**Note:** This is typically handled by the backend, but if your frontend handles it:

```javascript
// Extract tokens from callback
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');
const state = urlParams.get('state'); // Referral code if present

// Exchange code for tokens
const response = await fetch(`https://api.artemis.ares.codes/auth/google/callback?code=${code}&state=${state}`);
const data = await response.json();

// Store tokens
localStorage.setItem('access_token', data.access_token);
localStorage.setItem('refresh_token', data.refresh_token);

// Redirect to dashboard
window.location.href = '/dashboard';
```

---

## Testing

### Test Referral Link

1. Get a referral code from a user:
   ```bash
   curl -H "Authorization: Bearer <token>" \
     https://api.artemis.ares.codes/referral/code
   ```

2. Use the referral link:
   ```
   https://artemis.ares.codes/auth/google/login?state=ARTEMIS-0XZ9DS
   ```

3. Sign up with a new Google account

4. Verify referral was tracked:
   ```bash
   curl -H "Authorization: Bearer <referrer_token>" \
     https://api.artemis.ares.codes/referral/stats
   ```

---

## Common Issues & Solutions

### Issue 1: Referral code not being tracked

**Solution:** Ensure the `state` parameter is passed to the OAuth endpoint:
```javascript
// ✅ Correct
window.location.href = `https://api.artemis.ares.codes/auth/google/login?state=ARTEMIS-0XZ9DS`;

// ❌ Wrong - missing state parameter
window.location.href = 'https://api.artemis.ares.codes/auth/google/login';
```

### Issue 2: Referral link shows 404

**Solution:** Make sure your frontend route handles `/auth/google/login`:
```javascript
// In your router
router.get('/auth/google/login', (req, res) => {
  const referralCode = req.query.state;
  // Redirect to backend OAuth
  res.redirect(`https://api.artemis.ares.codes/auth/google/login?state=${referralCode}`);
});
```

### Issue 3: State parameter lost during OAuth

**Solution:** The backend handles this automatically. If you're implementing custom OAuth flow, ensure you pass `state` to Google:
```javascript
// The backend does this automatically, but if implementing custom:
const googleAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?
  client_id=${CLIENT_ID}&
  redirect_uri=${REDIRECT_URI}&
  response_type=code&
  scope=openid email profile&
  state=${referralCode}`; // ← Important: include state
```

---

## Summary

1. **Referral links format:** `https://artemis.ares.codes/auth/google/login?state=ARTEMIS-XXXXXX`
2. **Frontend should:** Redirect to backend OAuth endpoint with `state` parameter
3. **Backend handles:** OAuth flow, state preservation, referral tracking
4. **No extra API calls needed:** Referral tracking is automatic
5. **Test with:** A real referral code from `/api/referral/code` endpoint

---

## Support

If you encounter issues:
1. Check that the referral code starts with `ARTEMIS-`
2. Verify the `state` parameter is passed to `/api/auth/google/login`
3. Check backend logs for referral tracking errors
4. Ensure the user is signing up for the first time (not logging in)

---

## Quick Reference

| Action | Endpoint | Method | Auth Required |
|--------|----------|--------|---------------|
| Get referral code | `/api/referral/code` | GET | Yes |
| Get referral stats | `/api/referral/stats` | GET | Yes |
| Get points balance | `/api/referral/points` | GET | Yes |
| Google OAuth login | `/api/auth/google/login?state=CODE` | GET | No |
| OAuth callback | `/api/auth/google/callback` | GET | No |

---

**Last Updated:** 2025-12-31

