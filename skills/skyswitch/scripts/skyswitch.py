#!/usr/bin/env python3
"""
SkySwitch Telco API CLI

Manage PBX domains, VIP routing (route-by-ANI), and other SkySwitch operations.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

CONFIG_PATH = Path.home() / ".config" / "skyswitch" / "config.json"
TOKEN_CACHE_PATH = Path.home() / ".config" / "skyswitch" / "token.json"
API_BASE = "https://api.skyswitch.com"


def load_config() -> dict:
    """Load configuration from config file."""
    if not CONFIG_PATH.exists():
        print(f"Error: Config file not found at {CONFIG_PATH}", file=sys.stderr)
        print("Create it with client_id, client_secret, username, password, default_account_id", file=sys.stderr)
        sys.exit(1)
    
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_token(token_data: dict):
    """Cache the access token."""
    TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    token_data["cached_at"] = time.time()
    with open(TOKEN_CACHE_PATH, "w") as f:
        json.dump(token_data, f)
    os.chmod(TOKEN_CACHE_PATH, 0o600)


def load_cached_token() -> dict | None:
    """Load cached token if valid."""
    if not TOKEN_CACHE_PATH.exists():
        return None
    
    with open(TOKEN_CACHE_PATH) as f:
        data = json.load(f)
    
    # Check if token is expired (with 5 min buffer)
    cached_at = data.get("cached_at", 0)
    expires_in = data.get("expires_in", 0)
    if time.time() > cached_at + expires_in - 300:
        return None
    
    return data


def get_access_token(config: dict, force_refresh: bool = False) -> str:
    """Get a valid access token, refreshing if needed."""
    if not force_refresh:
        cached = load_cached_token()
        if cached:
            return cached["access_token"]
    
    # Request new token
    response = requests.post(
        f"{API_BASE}/oauth/token",
        data={
            "grant_type": "password",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "username": config["username"],
            "password": config["password"],
            "scope": "pbx account",
        },
    )
    
    if response.status_code != 200:
        print(f"Error getting token: {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)
        sys.exit(1)
    
    token_data = response.json()
    save_token(token_data)
    return token_data["access_token"]


def api_request(method: str, endpoint: str, config: dict, params: dict = None, retry: bool = True) -> dict:
    """Make an authenticated API request."""
    token = get_access_token(config)
    
    url = f"{API_BASE}{endpoint}"
    if params:
        url = f"{url}?{urlencode(params)}"
    
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.request(method, url, headers=headers)
    
    # Handle 401 by refreshing token
    if response.status_code == 401 and retry:
        token = get_access_token(config, force_refresh=True)
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.request(method, url, headers=headers)
    
    if response.status_code not in (200, 201, 204):
        print(f"API Error: {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)
        sys.exit(1)
    
    if response.status_code == 204:
        return {}
    
    return response.json() if response.text else {}


def cmd_token(args, config: dict):
    """Get/display access token."""
    token = get_access_token(config, force_refresh=args.refresh)
    if args.quiet:
        print(token)
    else:
        cached = load_cached_token()
        print(f"Access Token: {token[:50]}...")
        if cached:
            expires_at = cached.get("cached_at", 0) + cached.get("expires_in", 0)
            remaining = int(expires_at - time.time())
            print(f"Expires in: {remaining // 60} minutes")


def cmd_domains(args, config: dict):
    """List PBX domains."""
    account_id = args.account or config.get("default_account_id")
    if not account_id:
        print("Error: No account ID provided and no default set", file=sys.stderr)
        sys.exit(1)
    
    result = api_request("GET", f"/accounts/{account_id}/pbx/domains", config)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        domains = result.get("data", result) if isinstance(result, dict) else result
        if isinstance(domains, list):
            for d in domains:
                if isinstance(d, dict):
                    print(f"{d.get('domain', d.get('name', d))}")
                else:
                    print(d)
        else:
            print(json.dumps(result, indent=2))


def cmd_vip_list(args, config: dict):
    """List VIP routes (route-by-ANI)."""
    account_id = args.account or config.get("default_account_id")
    if not account_id:
        print("Error: No account ID provided and no default set", file=sys.stderr)
        sys.exit(1)
    
    params = {}
    if args.domain:
        params["domain"] = args.domain
    if args.ani:
        params["ani"] = args.ani
    if args.dnis:
        params["dnis"] = args.dnis
    
    result = api_request("GET", f"/accounts/{account_id}/pbx/route-by-ani", config, params)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        routes = result.get("data", result) if isinstance(result, dict) else result
        if isinstance(routes, list):
            if not routes:
                print("No VIP routes found")
            for r in routes:
                ani = r.get("ani", "?")
                dest = r.get("destination", "?")
                app = r.get("application", "")
                dnis = r.get("dnis", "")
                domain = r.get("domain", "")
                line = f"ANI: {ani} -> {dest}"
                if app:
                    line += f" ({app})"
                if dnis:
                    line += f" [DNIS: {dnis}]"
                if domain and not args.domain:
                    line += f" @ {domain}"
                print(line)
        else:
            print(json.dumps(result, indent=2))


def cmd_vip_add(args, config: dict):
    """Add a VIP route."""
    account_id = args.account or config.get("default_account_id")
    if not account_id:
        print("Error: No account ID provided and no default set", file=sys.stderr)
        sys.exit(1)
    
    if not args.ani or not args.domain or not args.destination:
        print("Error: --ani, --domain, and --destination are required", file=sys.stderr)
        sys.exit(1)
    
    params = {
        "ani": args.ani,
        "domain": args.domain,
        "destination": args.destination,
    }
    if args.dnis:
        params["dnis"] = args.dnis
    if args.application:
        params["application"] = args.application
    
    result = api_request("PUT", f"/accounts/{account_id}/pbx/route-by-ani", config, params)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"✓ Added VIP route: {args.ani} -> {args.destination}")


def cmd_vip_remove(args, config: dict):
    """Remove a VIP route."""
    account_id = args.account or config.get("default_account_id")
    if not account_id:
        print("Error: No account ID provided and no default set", file=sys.stderr)
        sys.exit(1)
    
    if not args.ani or not args.domain:
        print("Error: --ani and --domain are required", file=sys.stderr)
        sys.exit(1)
    
    params = {
        "ani": args.ani,
        "domain": args.domain,
    }
    if args.dnis:
        params["dnis"] = args.dnis
    
    api_request("DELETE", f"/accounts/{account_id}/pbx/route-by-ani", config, params)
    print(f"✓ Removed VIP route for {args.ani}")


def main():
    parser = argparse.ArgumentParser(description="SkySwitch Telco API CLI")
    parser.add_argument("--account", "-a", help="Account ID (overrides default)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # token command
    token_parser = subparsers.add_parser("token", help="Get/display access token")
    token_parser.add_argument("--refresh", "-r", action="store_true", help="Force refresh")
    token_parser.add_argument("--quiet", "-q", action="store_true", help="Print only token")
    
    # domains command
    domains_parser = subparsers.add_parser("domains", help="List PBX domains")
    
    # vip command group
    vip_parser = subparsers.add_parser("vip", help="VIP routing (route-by-ANI)")
    vip_subparsers = vip_parser.add_subparsers(dest="vip_command", help="VIP command")
    
    # vip list
    vip_list = vip_subparsers.add_parser("list", help="List VIP routes")
    vip_list.add_argument("--domain", "-d", help="Filter by domain")
    vip_list.add_argument("--ani", help="Filter by ANI")
    vip_list.add_argument("--dnis", help="Filter by DNIS")
    
    # vip add
    vip_add = vip_subparsers.add_parser("add", help="Add VIP route")
    vip_add.add_argument("--ani", required=True, help="Caller ANI (phone number)")
    vip_add.add_argument("--domain", "-d", required=True, help="PBX domain")
    vip_add.add_argument("--destination", required=True, help="Route destination")
    vip_add.add_argument("--dnis", help="Called number (optional)")
    vip_add.add_argument("--application", choices=["user", "device", "literal"], 
                         default="user", help="Destination type")
    
    # vip remove
    vip_remove = vip_subparsers.add_parser("remove", help="Remove VIP route")
    vip_remove.add_argument("--ani", required=True, help="Caller ANI")
    vip_remove.add_argument("--domain", "-d", required=True, help="PBX domain")
    vip_remove.add_argument("--dnis", help="Called number (optional)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    config = load_config()
    
    if args.command == "token":
        cmd_token(args, config)
    elif args.command == "domains":
        cmd_domains(args, config)
    elif args.command == "vip":
        if not args.vip_command:
            vip_parser.print_help()
            sys.exit(1)
        if args.vip_command == "list":
            cmd_vip_list(args, config)
        elif args.vip_command == "add":
            cmd_vip_add(args, config)
        elif args.vip_command == "remove":
            cmd_vip_remove(args, config)


if __name__ == "__main__":
    main()
