---
name: skyswitch
description: SkySwitch Telco API for PBX management, VIP routing, inventory, and provisioning. Use when managing SkySwitch/NumberShift customer phone systems, configuring route-by-ANI (VIP caller lists), or querying PBX domains and users. Supports Boundary by NumberShift VIP features.
---

# SkySwitch API Skill

Interact with SkySwitch Telco API for PBX and telecom operations.

## Quick Start

```bash
# List VIP routes for a domain
skyswitch vip list --domain example.skyswitch.net

# Add a VIP caller (bypasses after-hours, routes direct)
skyswitch vip add --ani 16165551234 --domain example.skyswitch.net --destination user:john

# Remove a VIP caller
skyswitch vip remove --ani 16165551234 --domain example.skyswitch.net

# List PBX domains
skyswitch domains --account 12345
```

## CLI Reference

Located at `scripts/skyswitch.py`. Requires config at `~/.config/skyswitch/config.json`:

```json
{
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET",
  "username": "YOUR_USERNAME",
  "password": "YOUR_PASSWORD",
  "default_account_id": "12345"
}
```

### Commands

| Command | Description |
|---------|-------------|
| `vip list` | List route-by-ANI rules (VIP callers) |
| `vip add` | Add a VIP caller route |
| `vip remove` | Remove a VIP caller route |
| `domains` | List PBX domains for an account |
| `token` | Get/refresh OAuth token (debug) |

### VIP Routing (Route-by-ANI)

Used by **Boundary by NumberShift** for VIP caller lists that bypass normal call routing.

```bash
# List all VIP routes for a domain
skyswitch vip list --domain customer.skyswitch.net

# Filter by specific DID
skyswitch vip list --domain customer.skyswitch.net --dnis 16165559999

# Add VIP: route caller directly to a user
skyswitch vip add \
  --ani 16165551234 \
  --domain customer.skyswitch.net \
  --destination user:john \
  --application user

# Add VIP: route to a specific device
skyswitch vip add \
  --ani 16165551234 \
  --domain customer.skyswitch.net \
  --destination device:johns-cell \
  --application device

# Add VIP: route to a literal SIP URI
skyswitch vip add \
  --ani 16165551234 \
  --domain customer.skyswitch.net \
  --destination sip:+16165559999@carrier.net \
  --application literal

# Remove VIP route
skyswitch vip remove --ani 16165551234 --domain customer.skyswitch.net
```

**Application types:**
- `user` — Route to a PBX user
- `device` — Route to a specific device
- `literal` — Route to a SIP URI directly

## NumberShift / Boundary Notes

Boundary by NumberShift uses route-by-ANI for VIP caller features:

- **VIP List**: Callers who bypass after-hours routing and ring through directly
- **Implementation**: Each VIP is a route-by-ANI rule with `application=user` pointing to the subscriber
- **Domain**: Each Boundary customer has a SkySwitch PBX domain
- **Account**: NumberShift reseller account ID manages all Boundary customers

### ⚠️ CRITICAL: First-Time Domain Setup

**VIP lists won't work without this one-time setup per domain:**

1. **Open SkySwitch Support Ticket** — Request a Dial Translation Rule for unmatched ANIs
   - Provide: Domain name + fallback destination (where non-VIP calls should go)
   - Support sets up backend rule to route unmatched callers
   - Allow 1 business day for implementation
   - **Without this, only VIP callers get through — everyone else is dropped!**

2. **Create `route_by_ani` User in PBX**
   - Create user named "Route By ANI" or similar
   - No device assigned
   - Voicemail disabled
   - Add Answering Rule: Forward Always to `route_by_ani`

3. **Point DID to the ANI User**
   - Route the customer's phone number to the route_by_ani user
   - This invokes the ANI routing logic

**Only after these steps** can you manage VIP routes via API.

### Boundary Provisioning Workflow

For each new Boundary customer:
1. Create PBX domain (if new)
2. **Submit support ticket for dial translation rule** ← BLOCKER
3. Create route_by_ani user with forwarding rule
4. Route customer DID to route_by_ani user
5. Now API can manage VIP list: `skyswitch vip add/remove`

### Automation TODO

The support ticket step is manual. Investigate:
- Can dial translation rules be created via API? (Check with SkySwitch)
- Can route_by_ani user creation be automated via PBX API?
- Goal: Fully automate Boundary customer provisioning

## Authentication

OAuth 2.0 password grant. Token auto-refreshes. Scope required: `pbx`.

See `references/api.md` for full API documentation.

## Setup

1. Get client_id and client_secret from SkySwitch Control Tower
2. Create config file:
   ```bash
   mkdir -p ~/.config/skyswitch
   cat > ~/.config/skyswitch/config.json << 'EOF'
   {
     "client_id": "YOUR_CLIENT_ID",
     "client_secret": "YOUR_CLIENT_SECRET",
     "username": "YOUR_USERNAME",
     "password": "YOUR_PASSWORD",
     "default_account_id": "YOUR_ACCOUNT_ID"
   }
   EOF
   chmod 600 ~/.config/skyswitch/config.json
   ```
3. Test: `skyswitch token`
