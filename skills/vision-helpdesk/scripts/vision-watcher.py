#!/usr/bin/env python3
"""
Vision Helpdesk Ticket Watcher - Monitor for new/updated tickets and alert via webhook.

Usage:
    vision-watcher [--profile PROFILE] [--state-file PATH] [--webhook-url URL] [--quiet]
    
Environment:
    VISION_WATCHER_WEBHOOK - Discord/Slack webhook URL for alerts
    VISION_WATCHER_STATE   - Path to state file (default: ~/.vision-watcher-state.json)
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

DEFAULT_STATE_FILE = os.path.expanduser("~/.vision-watcher-state.json")
DEFAULT_LOOKBACK_HOURS = 2


def get_credentials(profile: str = "20859") -> dict:
    """Load credentials from pass."""
    paths_to_try = [
        f"vision/{profile}",
        f"{profile}/visionhelpdesk/env"
    ]
    
    for path in paths_to_try:
        try:
            result = subprocess.run(
                ["pass", path],
                capture_output=True, text=True, check=True
            )
            creds = {}
            for line in result.stdout.strip().split("\n"):
                if "=" in line and not line.strip().startswith("#"):
                    key, value = line.split("=", 1)
                    creds[key.strip()] = value.strip().strip('"')
            
            normalized = {}
            if "VISION_TOKEN" in creds:
                normalized["token"] = creds["VISION_TOKEN"]
            if "token" in creds:
                normalized["token"] = creds["token"]
            normalized["url"] = creds.get("url", "https://clients.sipcapturer.com/api/index.php")
            
            if normalized.get("token"):
                return normalized
        except subprocess.CalledProcessError:
            continue
    
    raise RuntimeError(f"Could not load credentials for profile {profile}")


def api_request(operation: str, params: dict, profile: str = "20859") -> dict:
    """Make an API request to Vision Helpdesk."""
    creds = get_credentials(profile)
    
    request_params = {
        "vis_txttoken": creds["token"],
        "vis_module": "ticket",
        "vis_operation": operation,
        "vis_encode": "json",
        **params
    }
    
    response = requests.get(creds["url"], params=request_params, timeout=30)
    response.raise_for_status()
    return response.json()


def load_state(state_file: str) -> dict:
    """Load watcher state from file."""
    path = Path(state_file)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"seen_tickets": {}, "last_check": None}


def save_state(state: dict, state_file: str) -> None:
    """Save watcher state to file."""
    Path(state_file).write_text(json.dumps(state, indent=2))


def format_timestamp(ts: str) -> str:
    """Convert Unix timestamp to readable date."""
    try:
        dt = datetime.fromtimestamp(int(ts))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(ts)


def send_discord_alert(webhook_url: str, title: str, tickets: list, color: int = 0x00ff00) -> None:
    """Send alert to Discord webhook."""
    if not tickets:
        return
    
    # Build embed fields for each ticket
    fields = []
    for t in tickets[:10]:  # Discord limit
        priority = t.get("priority", "?")
        status = t.get("status", "?")
        company = t.get("company_name", "Unknown")[:30]
        subject = t.get("subject", "No subject")[:100]
        ticket_hash = t.get("ticket_hash", t.get("ticket_id", "?"))
        modified = format_timestamp(t.get("modify_date", ""))
        
        # Color code by priority
        priority_emoji = {"Urgent": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(priority, "⚪")
        
        fields.append({
            "name": f"{priority_emoji} {ticket_hash} — {status}",
            "value": f"**{subject}**\n{company} • {modified}",
            "inline": False
        })
    
    embed = {
        "title": title,
        "color": color,
        "fields": fields,
        "footer": {"text": f"Vision Helpdesk • {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
    }
    
    if len(tickets) > 10:
        embed["footer"]["text"] += f" • +{len(tickets) - 10} more"
    
    payload = {"embeds": [embed]}
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to send Discord alert: {e}", file=sys.stderr)


def get_ticket_details(ticket_id: str, profile: str = "20859") -> dict:
    """Fetch full ticket details including conversation."""
    params = {"vis_ticket_id": ticket_id}
    try:
        result = api_request("ticket_details", params, profile)
        return result
    except Exception:
        return {}


def triage_with_claude(ticket: dict, ticket_details: dict) -> str:
    """Call Claude CLI to generate triage summary."""
    ticket_hash = ticket.get("ticket_hash", "?")
    subject = ticket.get("subject", "No subject")
    company = ticket.get("company_name", "Unknown") or "Unknown"
    priority = ticket.get("priority", "?")
    email = ticket.get("email", "")
    
    # Extract content from details
    content = ticket_details.get("content", "") if ticket_details else ""
    # Strip HTML for cleaner input
    import re
    content_text = re.sub(r'<[^>]+>', ' ', content)
    content_text = re.sub(r'\s+', ' ', content_text).strip()[:2000]
    
    prompt = f"""Triage this support ticket. Even if you can't gather telecom context, ALWAYS provide a useful summary.

Ticket: {ticket_hash}
Subject: {subject}
Company: {company}
Priority: {priority}
From: {email}

Content:
{content_text}

Respond with this EXACT format (fill in the brackets):

**Summary:** [One sentence: what does the customer need?]
**Category:** [routing | voicemail | hardware | billing | access | spam | other]
**Urgency:** [🔴 High - service down/urgent | 🟡 Medium - needs attention today | 🟢 Low - can wait | ⚪ None - spam/auto-reply]
**Action:** [What should a tech do? Or "Ignore - spam" / "Close - auto-reply" if not actionable]

Rules:
- ALWAYS fill in all 4 fields, even for spam/junk tickets
- If it's spam, marketing, or an auto-reply: Category=spam, Urgency=⚪ None, Action=Ignore
- If it's billing/invoice related: Category=billing, suggest forwarding to accounting
- Keep total response under 400 chars
- No extra commentary"""

    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            # Fallback: generate minimal triage without Claude
            return generate_fallback_triage(ticket, subject, content_text)
    except subprocess.TimeoutExpired:
        return generate_fallback_triage(ticket, subject, content_text, reason="timeout")
    except Exception as e:
        return generate_fallback_triage(ticket, subject, content_text, reason=str(e)[:50])


def generate_fallback_triage(ticket: dict, subject: str, content: str, reason: str = "") -> str:
    """Generate a basic triage when Claude fails."""
    import re
    
    subject_lower = subject.lower()
    content_lower = content.lower()[:500]
    combined = subject_lower + " " + content_lower
    
    # Detect spam/marketing
    spam_signals = ["unsubscribe", "click here", "act now", "limited time", "invoice attached", 
                    "get funds", "eligible invoices", "marketing", "newsletter"]
    if any(sig in combined for sig in spam_signals):
        return "**Summary:** Likely spam or marketing email\n**Category:** spam\n**Urgency:** ⚪ None\n**Action:** Ignore - spam/marketing"
    
    # Detect auto-replies (but not requests mentioning "out of office")
    auto_signals = ["automatic reply", "auto-reply", "autoreply", "i am currently out", "i will be out of the office", 
                    "i'm currently out", "thank you for your email", "i will respond when i return"]
    # Only match auto-reply if it looks like a bounce, not a request
    request_signals = ["please", "need", "want", "can you", "could you", "forward", "change", "update"]
    is_request = any(sig in combined for sig in request_signals)
    if any(sig in combined for sig in auto_signals) and not is_request:
        return "**Summary:** Auto-reply/OOO message\n**Category:** other\n**Urgency:** ⚪ None\n**Action:** Close - auto-reply"
    
    # Detect billing
    billing_signals = ["invoice", "payment", "billing", "charge", "receipt", "account balance"]
    if any(sig in combined for sig in billing_signals):
        return f"**Summary:** {subject[:60]}\n**Category:** billing\n**Urgency:** 🟢 Low\n**Action:** Forward to accounting"
    
    # Detect urgent issues
    urgent_signals = ["down", "not working", "emergency", "urgent", "asap", "can't make calls", "no dial tone"]
    if any(sig in combined for sig in urgent_signals):
        urgency = "🔴 High"
    elif any(sig in combined for sig in ["forwarding", "routing", "voicemail", "greeting"]):
        urgency = "🟡 Medium"
    else:
        urgency = "🟡 Medium"
    
    # Detect category
    if any(sig in combined for sig in ["forward", "routing", "route", "transfer", "redirect"]):
        category = "routing"
    elif any(sig in combined for sig in ["voicemail", "vm", "greeting", "message"]):
        category = "voicemail"
    elif any(sig in combined for sig in ["phone", "handset", "device", "hardware"]):
        category = "hardware"
    else:
        category = "other"
    
    reason_note = f" (fallback: {reason})" if reason else ""
    return f"**Summary:** {subject[:60]}\n**Category:** {category}\n**Urgency:** {urgency}\n**Action:** Review ticket{reason_note}"


def post_triage_to_discord(webhook_url: str, ticket: dict, triage_summary: str) -> None:
    """Post triage summary to Discord webhook."""
    ticket_hash = ticket.get("ticket_hash", "?")
    ticket_id = ticket.get("ticket_id", "")
    subject = ticket.get("subject", "No subject")[:80]
    priority = ticket.get("priority", "?")
    company = ticket.get("company_name", "Unknown")
    
    # Build ticket URL
    ticket_url = f"https://clients.sipcapturer.com/manage/#/ticket/ticket_details/{ticket_hash}/{ticket_id}"
    
    priority_emoji = {"Urgent": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(priority, "⚪")
    
    embed = {
        "title": f"{priority_emoji} {ticket_hash}: {subject}",
        "url": ticket_url,
        "description": triage_summary[:2000],
        "color": {"Urgent": 0xff0000, "High": 0xff8800, "Medium": 0xffcc00, "Low": 0x00cc00}.get(priority, 0x888888),
        "footer": {"text": f"{company} • {datetime.now().strftime('%H:%M')}"}
    }
    
    try:
        response = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
        response.raise_for_status()
        print(f"Posted triage for {ticket_hash}")
    except requests.RequestException as e:
        print(f"Discord post failed: {e}", file=sys.stderr)


def post_triage_to_slack(channel: str, ticket: dict, triage_summary: str, bot_token: str) -> None:
    """Post triage summary to Slack channel using Bot API."""
    ticket_hash = ticket.get("ticket_hash", "?")
    ticket_id = ticket.get("ticket_id", "")
    subject = ticket.get("subject", "No subject")[:80]
    priority = ticket.get("priority", "?")
    company = ticket.get("company_name", "Unknown") or "Unknown"
    
    # Build ticket URL
    ticket_url = f"https://clients.sipcapturer.com/manage/#/ticket/ticket_details/{ticket_hash}/{ticket_id}"
    
    priority_emoji = {"Urgent": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(priority, "⚪")
    
    # Build Slack blocks
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{priority_emoji} {ticket_hash}: {subject}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": triage_summary[:2900]
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*{company}* • {priority} • {datetime.now().strftime('%H:%M')} • <{ticket_url}|View Ticket>"
                }
            ]
        },
        {"type": "divider"}
    ]
    
    payload = {
        "channel": channel,
        "text": f"{priority_emoji} {ticket_hash}: {subject}",
        "blocks": blocks,
        "unfurl_links": False
    }
    
    try:
        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            json=payload,
            headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"},
            timeout=10
        )
        result = response.json()
        if result.get("ok"):
            print(f"Posted triage for {ticket_hash} to Slack #{channel}")
        else:
            print(f"Slack post failed: {result.get('error')}", file=sys.stderr)
    except requests.RequestException as e:
        print(f"Slack post failed: {e}", file=sys.stderr)


def should_skip_ticket(ticket: dict) -> tuple[bool, str]:
    """
    Check if a ticket should be skipped (not triaged or posted).
    Returns (should_skip, reason).
    """
    subject = (ticket.get("subject") or "").lower()
    company = (ticket.get("company_name") or "").lower()
    email = (ticket.get("email") or "").lower()
    
    # Skip billing/funding/invoice tickets
    billing_keywords = [
        "invoice", "payment", "funding", "funds", "billing", 
        "receipt", "statement", "balance due", "pay now",
        "eligible invoices", "get funds", "received your invoice"
    ]
    if any(kw in subject for kw in billing_keywords):
        return True, "billing/invoice"
    
    # Skip known spam/marketing senders
    spam_domains = ["marketing", "newsletter", "promo", "noreply@"]
    if any(sd in email for sd in spam_domains):
        return True, "spam sender"
    
    # Skip auto-generated system emails
    system_keywords = ["automatic notification", "do not reply", "system alert"]
    if any(kw in subject for kw in system_keywords):
        return True, "system notification"
    
    return False, ""


def triage_tickets_immediately(
    tickets: list, 
    profile: str = "20859",
    slack_channel: Optional[str] = None,
    slack_token: Optional[str] = None,
    discord_webhook: Optional[str] = None
) -> None:
    """Triage tickets using Claude CLI and post to Slack/Discord immediately."""
    triaged_count = 0
    
    for ticket in tickets[:10]:  # Check up to 10, but may skip some
        if triaged_count >= 5:  # Limit actual triages to 5
            break
            
        ticket_id = ticket.get("ticket_id")
        ticket_hash = ticket.get("ticket_hash", "?")
        
        # Pre-filter: skip billing/spam/system tickets
        should_skip, skip_reason = should_skip_ticket(ticket)
        if should_skip:
            print(f"Skipping {ticket_hash} ({skip_reason})")
            continue
        
        print(f"Triaging {ticket_hash}...")
        triaged_count += 1
        
        # Get full ticket details
        details = get_ticket_details(ticket_id, profile) if ticket_id else {}
        
        # Call Claude for triage
        summary = triage_with_claude(ticket, details)
        
        # Post to Slack or Discord
        if slack_channel and slack_token:
            post_triage_to_slack(slack_channel, ticket, summary, slack_token)
        elif discord_webhook:
            post_triage_to_discord(discord_webhook, ticket, summary)
        else:
            print(f"--- {ticket_hash} ---")
            print(summary)
            print()


def check_tickets(profile: str, state: dict, lookback_hours: int = 2) -> tuple[list, list]:
    """
    Check for new and updated tickets.
    Returns (new_tickets, updated_tickets).
    """
    since = int((datetime.now() - timedelta(hours=lookback_hours)).timestamp())
    
    params = {
        "vis_filter": f"modify_date>{since}",
        "vis_details_req": 1,
        "vis_skip_info": 1,
        "vis_limit": "0,100"
    }
    
    result = api_request("get_tickets", params, profile)
    tickets = result.get("data", [])
    
    seen = state.get("seen_tickets", {})
    new_tickets = []
    updated_tickets = []
    
    for ticket in tickets:
        ticket_id = str(ticket.get("ticket_id", ""))
        if not ticket_id:
            continue
        
        modify_time = ticket.get("modify_date", "")
        
        if ticket_id not in seen:
            # New ticket
            new_tickets.append(ticket)
            seen[ticket_id] = {"modify_date": modify_time, "first_seen": datetime.now().isoformat()}
        elif seen[ticket_id].get("modify_date") != modify_time:
            # Updated ticket
            updated_tickets.append(ticket)
            seen[ticket_id]["modify_date"] = modify_time
            seen[ticket_id]["last_updated"] = datetime.now().isoformat()
    
    state["seen_tickets"] = seen
    state["last_check"] = datetime.now().isoformat()
    
    return new_tickets, updated_tickets


def filter_important(tickets: list) -> list:
    """Filter to only high/urgent priority tickets."""
    return [t for t in tickets if t.get("priority") in ("High", "Urgent")]


def main():
    parser = argparse.ArgumentParser(description="Vision Helpdesk Ticket Watcher")
    parser.add_argument("--profile", "-p", default="20859", help="Credential profile")
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE, help="State file path")
    parser.add_argument("--webhook-url", help="Discord/Slack webhook URL")
    parser.add_argument("--hours", type=int, default=DEFAULT_LOOKBACK_HOURS, help="Hours to look back")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only output on new tickets")
    parser.add_argument("--important-only", action="store_true", help="Only alert on high/urgent")
    parser.add_argument("--triage", action="store_true", help="Triage new tickets with Claude CLI")
    parser.add_argument("--slack-channel", help="Slack channel to post triage (e.g., htel-team)")
    parser.add_argument("--slack-token", help="Slack bot token (or use SLACK_BOT_TOKEN env)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    
    args = parser.parse_args()
    
    # Get webhook URL from args or environment
    webhook_url = args.webhook_url or os.environ.get("VISION_WATCHER_WEBHOOK")
    state_file = args.state_file or os.environ.get("VISION_WATCHER_STATE", DEFAULT_STATE_FILE)
    
    # Load state
    state = load_state(state_file)
    
    try:
        new_tickets, updated_tickets = check_tickets(args.profile, state, args.hours)
    except Exception as e:
        print(f"Error checking tickets: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Filter if requested
    if args.important_only:
        new_tickets = filter_important(new_tickets)
        updated_tickets = filter_important(updated_tickets)
    
    # Save state
    save_state(state, state_file)
    
    # Output
    if args.json:
        print(json.dumps({
            "new": new_tickets,
            "updated": updated_tickets,
            "timestamp": datetime.now().isoformat()
        }, indent=2))
        return
    
    if not args.quiet:
        print(f"Checked at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"New tickets: {len(new_tickets)}")
        print(f"Updated tickets: {len(updated_tickets)}")
    
    # Triage new tickets immediately using Claude CLI
    if args.triage and new_tickets:
        slack_token = args.slack_token or os.environ.get("SLACK_BOT_TOKEN")
        triage_tickets_immediately(
            new_tickets,
            profile=args.profile,
            slack_channel=args.slack_channel,
            slack_token=slack_token,
            discord_webhook=webhook_url
        )
    elif webhook_url:
        # Just send basic alerts if not triaging
        if new_tickets:
            send_discord_alert(webhook_url, f"🎫 {len(new_tickets)} New Ticket(s)", new_tickets, color=0x00ff00)
        if updated_tickets:
            important_updates = filter_important(updated_tickets)
            if important_updates:
                send_discord_alert(webhook_url, f"🔄 {len(important_updates)} High-Priority Update(s)", important_updates, color=0xffaa00)
    
    # Exit code indicates new tickets
    if new_tickets:
        if not args.quiet:
            for t in new_tickets:
                print(f"  NEW: {t.get('ticket_hash')} - {t.get('subject', '')[:50]}")
        sys.exit(0)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
