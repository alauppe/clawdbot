# SkySwitch API Reference

Base URL: `https://api.skyswitch.com`

## Authentication

OAuth 2.0 password grant flow.

### Obtain Access Token

```
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=password
client_id=YOUR_CLIENT_ID
client_secret=YOUR_CLIENT_SECRET
username=YOUR_USERNAME
password=YOUR_PASSWORD
scope=pbx account
```

**Response:**
```json
{
  "token_type": "Bearer",
  "expires_in": 21600,
  "access_token": "eyJ0eXAi...",
  "refresh_token": "def502..."
}
```

### Using the Token

Include in Authorization header:
```
Authorization: Bearer eyJ0eXAi...
```

### Scopes

| Scope | Description |
|-------|-------------|
| `pbx` | Manage PBX features (domains, route-by-ani, etc.) |
| `account` | Access account information |
| `user` | Manage users |
| `routing` | Manage phone number routing |
| `phone_number` | Manage inventory |
| `e911` | Manage E911 services |
| `messaging` | Manage SMS/MMS |

## Route-by-ANI (VIP Routing)

### List Routes

```
GET /accounts/{account_id}/pbx/route-by-ani
```

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| ani | string | No | Filter by caller ANI |
| dnis | string | No | Filter by called number |
| domain | string | No | Filter by PBX domain |

**Response:**
```json
[
  {
    "ani": "16165551234",
    "dnis": "16165559999",
    "domain": "customer.skyswitch.net",
    "application": "user",
    "destination": "john"
  }
]
```

### Create/Update Route

```
PUT /accounts/{account_id}/pbx/route-by-ani
```

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| ani | string | Yes | Caller ANI to match |
| domain | string | Yes | PBX domain |
| destination | string | Yes | Route destination |
| dnis | string | No | Called number to match |
| application | string | No | "user", "device", or "literal" |

**Response:** 201 Created

### Delete Route

```
DELETE /accounts/{account_id}/pbx/route-by-ani
```

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| ani | string | Yes | Caller ANI |
| domain | string | Yes | PBX domain |
| dnis | string | No | Called number |

**Response:** 204 No Content

## PBX Domains

### List Domains

```
GET /accounts/{account_id}/pbx/domains
```

**Response:**
```json
[
  {
    "domain": "customer.skyswitch.net",
    "description": "Customer PBX"
  }
]
```

## Error Handling

| Status | Description |
|--------|-------------|
| 400 | Bad request (invalid parameters) |
| 401 | Unauthorized (token expired/invalid) |
| 403 | Forbidden (insufficient scope) |
| 404 | Resource not found |
| 500 | Server error |

Error response format:
```json
{
  "error": "error_code",
  "message": "Human readable message"
}
```
