# Passkey Management

## Overview

Access to the 3DPharma app is protected by passkeys. Each passkey:
- Is a short (~12-15 character) alphanumeric string
- Has a validity duration encoded inside it (lifetime, or N hours from first use)
- Starts counting down **only from the first time it is used**
- Cannot be forged or modified without breaking the encoding

---

## Generating Passkeys

Run `generate_passkey.py` from the backend directory.

### Single passkey

```bash
# Lifetime key (never expires)
python generate_passkey.py

# Valid for 2 hours from first use
python generate_passkey.py --hours 2

# Valid for 1 day (24h) from first use
python generate_passkey.py --hours 24

# Valid for 1 week (168h) from first use
python generate_passkey.py --hours 168
```

### Multiple passkeys at once

Use `--count` to generate a batch:

```bash
# 500 keys valid for 2 hours
python generate_passkey.py --hours 2 --count 500

# 100 keys valid for 24 hours
python generate_passkey.py --hours 24 --count 100

# 50 lifetime keys
python generate_passkey.py --count 50
```

### Save to a file

Redirect output to a text file for easy distribution:

```bash
python generate_passkey.py --hours 2 --count 500 > passkeys_2h.txt
```

---

## How Validity Works

| Scenario | Behaviour |
|---|---|
| Key used for the first time | Timer starts, access granted |
| Key used again within validity window | Access granted |
| Key used after validity window expires | Access denied, expiry time shown |
| Lifetime key (`--hours` omitted) | Always grants access |

---

## Distributing Passkeys

- Each passkey is **single-user** — share one key per person
- Keys are one-time-start: the clock starts on **first use**, not on creation
- Revocation is not currently supported — expired keys are automatically rejected

---

## Storage

First-use timestamps are stored in `passkey_store.json` in the backend directory. Do not delete this file or previously issued keys will reset their timers.

---

## API Endpoint

The passkey validation is handled by the backend API:

**Endpoint**: `POST /passkey/validate`

**Request Body**:
```json
{
  "passkey": "your-passkey-here"
}
```

**Response**:
```json
{
  "valid": true,
  "message": "Access granted."
}
```
