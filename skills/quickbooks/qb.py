#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "python-quickbooks",
#     "intuit-oauth",
# ]
# ///
"""
QuickBooks Online CLI - Interact with QBO API

Run with: uv run qb.py <command>
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
from quickbooks.objects.customer import Customer
from quickbooks.objects.invoice import Invoice
from quickbooks.objects.account import Account
from quickbooks.objects.item import Item
from quickbooks.objects.vendor import Vendor
from quickbooks.objects.bill import Bill
from quickbooks.objects.payment import Payment
from quickbooks.objects.estimate import Estimate


def get_pass(key: str) -> str:
    """Get value from pass password store"""
    try:
        result = subprocess.run(["pass", f"quickbooks/{key}"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    # Fallback to environment
    return os.environ.get(f"QB_{key.upper()}", "")


def save_pass(key: str, value: str):
    """Save value to pass password store"""
    try:
        proc = subprocess.Popen(
            ["pass", "insert", "-f", f"quickbooks/{key}"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        proc.communicate(input=f"{value}\n{value}\n")
    except Exception as e:
        print(f"Warning: Could not save to pass: {e}", file=sys.stderr)


def get_client() -> QuickBooks:
    """Initialize QuickBooks client with stored credentials"""
    client_id = get_pass("client_id")
    client_secret = get_pass("client_secret")
    refresh_token = get_pass("refresh_token")
    company_id = get_pass("company_id")
    environment = os.environ.get("QB_ENVIRONMENT", "sandbox")
    
    if not all([client_id, client_secret, refresh_token, company_id]):
        print("Missing credentials. Run 'qb.py auth' first or set up pass entries:", file=sys.stderr)
        print("  pass insert quickbooks/client_id", file=sys.stderr)
        print("  pass insert quickbooks/client_secret", file=sys.stderr)
        print("  pass insert quickbooks/refresh_token", file=sys.stderr)
        print("  pass insert quickbooks/company_id", file=sys.stderr)
        sys.exit(1)
    
    auth_client = AuthClient(
        client_id=client_id,
        client_secret=client_secret,
        environment=environment,
        redirect_uri="http://localhost:8000/callback",
    )
    
    client = QuickBooks(
        auth_client=auth_client,
        refresh_token=refresh_token,
        company_id=company_id,
        minorversion=75,  # Latest stable
    )
    
    # Save new refresh token if it changed
    if client.auth_client.refresh_token != refresh_token:
        save_pass("refresh_token", client.auth_client.refresh_token)
    
    return client


def to_dict(obj):
    """Convert QuickBooks object to dict for JSON output"""
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    elif hasattr(obj, '__dict__'):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
    return str(obj)


def cmd_customers(args):
    """List or search customers"""
    client = get_client()
    if args.search:
        customers = Customer.filter(DisplayName=f"%{args.search}%", qb=client)
    else:
        customers = Customer.all(max_results=args.limit, qb=client)
    
    result = [to_dict(c) for c in customers]
    print(json.dumps(result, indent=2, default=str))


def cmd_customer(args):
    """Get specific customer by ID"""
    client = get_client()
    customer = Customer.get(args.id, qb=client)
    print(json.dumps(to_dict(customer), indent=2, default=str))


def cmd_invoices(args):
    """List invoices"""
    client = get_client()
    if args.customer:
        invoices = Invoice.filter(CustomerRef=args.customer, qb=client)
    else:
        invoices = Invoice.all(max_results=args.limit, qb=client)
    
    result = [to_dict(i) for i in invoices]
    print(json.dumps(result, indent=2, default=str))


def cmd_invoice(args):
    """Get specific invoice by ID"""
    client = get_client()
    invoice = Invoice.get(args.id, qb=client)
    print(json.dumps(to_dict(invoice), indent=2, default=str))


def cmd_accounts(args):
    """List accounts (chart of accounts)"""
    client = get_client()
    if args.type:
        accounts = Account.filter(AccountType=args.type, qb=client)
    else:
        accounts = Account.all(max_results=args.limit, qb=client)
    
    result = [to_dict(a) for a in accounts]
    print(json.dumps(result, indent=2, default=str))


def cmd_vendors(args):
    """List vendors"""
    client = get_client()
    vendors = Vendor.all(max_results=args.limit, qb=client)
    result = [to_dict(v) for v in vendors]
    print(json.dumps(result, indent=2, default=str))


def cmd_items(args):
    """List items (products/services)"""
    client = get_client()
    items = Item.all(max_results=args.limit, qb=client)
    result = [to_dict(i) for i in items]
    print(json.dumps(result, indent=2, default=str))


def cmd_query(args):
    """Run raw query"""
    client = get_client()
    from quickbooks.objects.base import QuickbooksBaseObject
    result = QuickbooksBaseObject.query(args.query, qb=client)
    print(json.dumps([to_dict(r) for r in result], indent=2, default=str))


def cmd_auth(args):
    """Start OAuth flow to get tokens"""
    client_id = args.client_id or get_pass("client_id") or input("Client ID: ")
    client_secret = args.client_secret or get_pass("client_secret") or input("Client Secret: ")
    
    auth_client = AuthClient(
        client_id=client_id,
        client_secret=client_secret,
        environment=args.environment,
        redirect_uri="http://localhost:8000/callback",
    )
    
    scopes = [Scopes.ACCOUNTING]
    auth_url = auth_client.get_authorization_url(scopes)
    
    print(f"\n1. Open this URL in your browser:\n{auth_url}\n")
    print("2. Log in and authorize the app")
    print("3. You'll be redirected to localhost:8000/callback?code=...&realmId=...")
    
    callback_url = input("\n4. Paste the full callback URL here: ")
    
    # Parse the callback
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(callback_url)
    params = parse_qs(parsed.query)
    
    auth_code = params.get('code', [None])[0]
    realm_id = params.get('realmId', [None])[0]
    
    if not auth_code or not realm_id:
        print("Error: Could not parse code or realmId from callback URL", file=sys.stderr)
        sys.exit(1)
    
    # Exchange code for tokens
    auth_client.get_bearer_token(auth_code, realm_id=realm_id)
    
    print(f"\n✓ Authentication successful!")
    print(f"  Company ID: {realm_id}")
    print(f"  Access Token: {auth_client.access_token[:20]}...")
    print(f"  Refresh Token: {auth_client.refresh_token[:20]}...")
    
    # Save to pass
    save_pass("client_id", client_id)
    save_pass("client_secret", client_secret)
    save_pass("refresh_token", auth_client.refresh_token)
    save_pass("company_id", realm_id)
    
    print("\n✓ Credentials saved to pass store")


def cmd_create_invoice(args):
    """Create a new invoice"""
    client = get_client()
    
    from quickbooks.objects.invoice import Invoice
    from quickbooks.objects.detailline import SalesItemLine, SalesItemLineDetail
    from quickbooks.objects.base import Ref
    
    invoice = Invoice()
    invoice.CustomerRef = Ref()
    invoice.CustomerRef.value = args.customer
    
    # Parse line items: "Description:Amount" or "ItemRef:Qty:UnitPrice"
    invoice.Line = []
    for line_str in args.line:
        line = SalesItemLine()
        line.DetailType = "SalesItemLineDetail"
        line.SalesItemLineDetail = SalesItemLineDetail()
        
        parts = line_str.split(":")
        if len(parts) == 2:
            # Simple: Description:Amount
            line.Description = parts[0]
            line.Amount = float(parts[1])
            line.SalesItemLineDetail.Qty = 1
            line.SalesItemLineDetail.UnitPrice = float(parts[1])
        elif len(parts) >= 3:
            # Item ref: ItemRef:Qty:UnitPrice
            line.SalesItemLineDetail.ItemRef = Ref()
            line.SalesItemLineDetail.ItemRef.value = parts[0]
            line.SalesItemLineDetail.Qty = int(parts[1])
            line.SalesItemLineDetail.UnitPrice = float(parts[2])
            line.Amount = line.SalesItemLineDetail.Qty * line.SalesItemLineDetail.UnitPrice
        
        invoice.Line.append(line)
    
    invoice.save(qb=client)
    print(json.dumps(to_dict(invoice), indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="QuickBooks Online CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Customers
    p = subparsers.add_parser("customers", help="List customers")
    p.add_argument("--search", "-s", help="Search by display name")
    p.add_argument("--limit", "-l", type=int, default=100, help="Max results")
    p.set_defaults(func=cmd_customers)
    
    p = subparsers.add_parser("customer", help="Get customer by ID")
    p.add_argument("id", help="Customer ID")
    p.set_defaults(func=cmd_customer)
    
    # Invoices
    p = subparsers.add_parser("invoices", help="List invoices")
    p.add_argument("--customer", "-c", help="Filter by customer ID")
    p.add_argument("--limit", "-l", type=int, default=100, help="Max results")
    p.set_defaults(func=cmd_invoices)
    
    p = subparsers.add_parser("invoice", help="Get invoice by ID")
    p.add_argument("id", help="Invoice ID")
    p.set_defaults(func=cmd_invoice)
    
    p = subparsers.add_parser("create-invoice", help="Create invoice")
    p.add_argument("--customer", "-c", required=True, help="Customer ID")
    p.add_argument("--line", "-L", action="append", required=True, 
                   help="Line item: 'Description:Amount' or 'ItemRef:Qty:UnitPrice'")
    p.set_defaults(func=cmd_create_invoice)
    
    # Accounts
    p = subparsers.add_parser("accounts", help="List accounts")
    p.add_argument("--type", "-t", help="Filter by account type")
    p.add_argument("--limit", "-l", type=int, default=100, help="Max results")
    p.set_defaults(func=cmd_accounts)
    
    # Vendors
    p = subparsers.add_parser("vendors", help="List vendors")
    p.add_argument("--limit", "-l", type=int, default=100, help="Max results")
    p.set_defaults(func=cmd_vendors)
    
    # Items
    p = subparsers.add_parser("items", help="List items")
    p.add_argument("--limit", "-l", type=int, default=100, help="Max results")
    p.set_defaults(func=cmd_items)
    
    # Query
    p = subparsers.add_parser("query", help="Run raw query")
    p.add_argument("query", help="Query string (e.g., 'SELECT * FROM Customer')")
    p.set_defaults(func=cmd_query)
    
    # Auth
    p = subparsers.add_parser("auth", help="OAuth flow to get tokens")
    p.add_argument("--client-id", help="Client ID")
    p.add_argument("--client-secret", help="Client Secret")
    p.add_argument("--environment", default="sandbox", choices=["sandbox", "production"])
    p.set_defaults(func=cmd_auth)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
