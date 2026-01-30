# Telecom Triage Skill

**Purpose:** Gather context from NetSapiens to help a technician quickly understand and resolve a customer request. You're not solving the problem — you're giving the tech everything they need to arrive at the solution fast.

## Automated Ticket Monitoring

The `vision-watcher` script polls Vision Helpdesk for new tickets every 15 minutes (zero tokens). When new tickets arrive, it wakes Clawdbot to perform triage.

**Manual trigger:**
```bash
vision-watcher --triage --hours 1
```

**Service control:**
```bash
# Load/start the watcher
launchctl load ~/Library/LaunchAgents/com.clawdbot.vision-watcher.plist

# Stop the watcher
launchctl unload ~/Library/LaunchAgents/com.clawdbot.vision-watcher.plist

# Check status
launchctl list | grep vision-watcher
```

**Logs:** `/tmp/vision-watcher.log` and `/tmp/vision-watcher.err`

## When to Use

Customer requests involving:
- Temporary call routing (meetings, holidays, closures)
- Voicemail or greeting changes
- Call forwarding adjustments
- "Route my calls to X during Y"

## Triage Workflow

### 1. Identify the Domain & User

From ticket context or request:
- Extract customer/domain name
- Search users for the person mentioned
- Search domain lists for the company name in descriptions

```bash
# Find the user
netsapiens users --domain customer.12345.service --search "Joni"
```

Note their extension and role context (receptionist, sales, etc.)

### 2. Find Relevant Routing Config

Look for the main routing subscriber or auto-attendant:

```bash
# List subscribers - look for "Main", "AA", "Reception", etc.
netsapiens subscribers --domain customer.12345.service
```

Common patterns:
- "Main RU" — ring-up/main line
- "Auto Attendant" or "AA"
- Subscriber matching company name

tip: can list TNs and lookup requesting subscriber's callid_nmbr, and follow destination.

### 3. Check Answer Rules

List answer rules for the relevant subscriber (requesting user, and relevant routing users):

```bash
netsapiens answer-rules --domain customer.12345.service --subscriber "Main RU"
```

Look for pre-configured routing options:
- "Temp Routing" — temporary overrides
- "Meeting" — during meetings
- "Holiday" — holiday hours
- "After Hours" — evening routing
- "Emergency" — weather/closure

### 4. Check Time Frames

See what time frames exist and their current windows:

```bash
netsapiens time-frames --domain customer.12345.service
```

Time frames are the **when** — they trigger answer rules. Look for:
- Date/time based frames (can add specific windows)
- Named frames matching answer rules above

### 5. Transcribe Greetings (Optional)

If you need to understand what a greeting says or does:

```bash
# Download and transcribe AA greeting
netsapiens greeting-download --domain customer.12345.service --subscriber "Auto Attendant" --type aa
whisper greeting.wav
```

This helps understand the purpose of different routing paths.

## Output Format

Provide the tech with a **triage summary**:

```
**Customer:** [Domain]
**Requester:** [Name] — [Extension] ([Role if known])
**Request:** [What they want in plain English]

**Current Config:**
- Main routing: [Subscriber name]
- Answer rules found: [List relevant ones]
- Time frames: [List with current windows]

**Likely Solution:**
[Which time frame/answer rule seems right, what window to add]

**Notes:**
[Any ambiguity, questions for customer, etc.]
```

## Key Principles

1. **Flexible naming** — Time frames aren't always called "Temp Routing". Could be Meeting, Holiday, Override, etc. Read what's there. 

2. **Context clues** — Receptionist usually means main line. Sales might have their own queue or RU. Manager might have direct DID.

3. **Don't assume** — If multiple options could work, list them. Let the tech decide.

4. **Surface unknowns** — If you can't find the user, or there's no obvious time frame, say so. Missing info is still useful info.

5. **Speed over perfection** — A quick 80% summary beats a slow 100% analysis. The tech knows the system.

## Example Triage

**Ticket:** "Joni needs calls to go to voicemail during her 11am meeting tomorrow"

**Triage:**
```
**Customer:** customer.12345.service
**Requester:** Joni Smith — x101 (Receptionist)
**Request:** Route calls to voicemail during 11am meeting tomorrow

**Current Config:**
- Main routing: "Main RU" (x100)
- Answer rules: Default, After Hours, Temp Routing, Holiday
- Time frames: 
  - Business Hours (M-F 8a-5p)
  - After Hours (inverse)
  - Temp Routing (date/time, currently empty)
  - Holiday (specific dates)

**Likely Solution:**
Add tomorrow 11:00-12:00 to "Temp Routing" time frame. 
Verify "Temp Routing" answer rule routes to Joni's VM or appropriate destination.

**Notes:**
- Confirm meeting duration (assumed 1 hour)
- Check if this is Joni's DID or the main line
```

## Tips

- `--profile` flag on netsapiens commands selects the reseller (20859, 23281, etc.)
- Ticket metadata often contains domain/customer info
- When in doubt, list more context rather than less
