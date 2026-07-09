# Passkey Implementation - Setup Guide

## Overview

The passkey authentication mechanism has been successfully implemented in the frontend project. This restricts access to public visitors by requiring a valid passkey to access the web application.

## What Was Implemented

### Backend (FastAPI)
1. **`backend/app/routers/passkey.py`** - Passkey validation endpoint with base62 encoding/decoding
2. **`backend/passkey_store.json`** - Storage file for first-use timestamps
3. **`backend/generate_passkey.py`** - Script to generate passkeys with different durations
4. **`backend/PASSKEYS.md`** - Complete documentation on passkey management
5. Updated `backend/app/routers/__init__.py` and `backend/main.py` to include passkey router

### Frontend (React/TypeScript)
1. **`frontend/src/lib/passkey.ts`** - Base62 encoding/decoding and validation logic
2. **`frontend/src/components/PasskeyAuth.tsx`** - Full-page authentication component
3. Updated `frontend/src/App.tsx` - Integrated passkey authentication with session management

## How It Works

1. **Passkey Generation**: Admin generates passkeys using `python generate_passkey.py`
   - Can create lifetime keys or time-limited keys (e.g., 2 hours, 24 hours, 1 week)
   - Each passkey is ~12-15 characters, base62-encoded

2. **First Use**: When a visitor enters a passkey for the first time:
   - Backend validates the passkey format
   - Records the first-use timestamp in `passkey_store.json`
   - Grants access

3. **Subsequent Uses**: When the same passkey is used again:
   - Backend checks if the time elapsed since first use is within the validity period
   - Grants or denies access accordingly
   - Lifetime keys never expire

4. **Session Management**: 
   - Authentication state is stored in browser's sessionStorage
   - Clears when browser is closed (once per browser session)
   - User must re-enter passkey when opening a new browser session

## Setup Instructions

### 1. Backend Setup

```bash
cd backend

# Install dependencies (if not already installed)
pip install -r requirements.txt

# Generate test passkeys
python generate_passkey.py --hours 24 --count 5

# Start the backend server
python main.py
```

The backend will run on `http://localhost:8000`

### 2. Frontend Setup

```bash
cd frontend

# Create .env file from example (if not exists)
cp .env.example .env

# Ensure VITE_API_URL is set correctly in .env
# VITE_API_URL=http://localhost:8000

# Install dependencies (if not already installed)
npm install

# Start the frontend development server
npm run dev
```

The frontend will run on `http://localhost:5173` (or another port if 5173 is busy)

### 3. Testing

1. Open the frontend in your browser
2. You should see the passkey authentication screen
3. Enter one of the generated passkeys
4. If valid, you'll be granted access to the application
5. Close the browser and reopen - you'll need to enter the passkey again (session-based)

## Generating Passkeys

### Examples:

```bash
# Generate 1 lifetime key (never expires)
python generate_passkey.py

# Generate 1 key valid for 2 hours from first use
python generate_passkey.py --hours 2

# Generate 10 keys valid for 24 hours
python generate_passkey.py --hours 24 --count 10

# Generate 500 keys valid for 1 week and save to file
python generate_passkey.py --hours 168 --count 500 > passkeys_1week.txt
```

## API Endpoint

**POST** `/passkey/validate`

**Request:**
```json
{
  "passkey": "ZE7WWHcy2"
}
```

**Response (Success):**
```json
{
  "valid": true,
  "message": "Access granted."
}
```

**Response (Expired):**
```json
{
  "valid": false,
  "message": "Passkey expired. It was valid for 24h from first use (2024-01-15 10:30 UTC)."
}
```

## Security Features

1. **Base62 Encoding**: Passkeys are encoded to prevent easy tampering
2. **Server-Side Validation**: All validation happens on the backend
3. **First-Use Tracking**: Timer starts only on first use, not on generation
4. **Session-Based**: Authentication clears when browser closes
5. **No Revocation Needed**: Expired keys are automatically rejected

## File Structure

```
backend/
├── app/
│   └── routers/
│       ├── passkey.py          # Passkey validation endpoint
│       └── __init__.py         # Updated to include passkey router
├── passkey_store.json          # First-use timestamps storage
├── generate_passkey.py         # Passkey generation script
├── PASSKEYS.md                 # Documentation
└── main.py                     # Updated to include passkey router

frontend/
├── src/
│   ├── components/
│   │   └── PasskeyAuth.tsx     # Authentication UI component
│   ├── lib/
│   │   └── passkey.ts          # Passkey utilities
│   └── App.tsx                 # Updated with auth integration
└── .env.example                # Environment variables
```

## Troubleshooting

### Frontend can't connect to backend
- Ensure backend is running on `http://localhost:8000`
- Check `VITE_API_URL` in frontend `.env` file
- Check browser console for CORS errors

### Passkey validation fails
- Ensure `passkey_store.json` exists and is writable
- Check backend logs for errors
- Verify passkey was generated correctly

### Authentication doesn't persist
- This is expected behavior - authentication is session-based
- It clears when browser closes
- User must re-enter passkey in new browser session

## Production Deployment

1. **Backend**: 
   - Ensure `passkey_store.json` is in a persistent location
   - Set appropriate CORS origins in `main.py`
   - Use environment variables for configuration

2. **Frontend**:
   - Set `VITE_API_URL` to production backend URL
   - Build: `npm run build`
   - Deploy the `dist` folder

3. **Passkey Distribution**:
   - Generate passkeys with appropriate durations
   - Distribute securely to authorized users
   - Keep `passkey_store.json` backed up

## Notes

- Each passkey is intended for single-user use
- Passkeys cannot be revoked (they expire naturally)
- The same mechanism from the OLD Streamlit project has been replicated
- All existing code remains unchanged - passkey logic is in separate files
