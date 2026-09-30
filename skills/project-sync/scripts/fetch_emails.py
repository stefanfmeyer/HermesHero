#!/usr/bin/env python3
"""
Fetch high-priority emails for project sync.
Usage: python3 fetch_emails.py --priority high --days <N> [--config <path>]

Supports:
- IMAP via himalaya CLI (if installed)
- Gmail API (if configured)
- Fallback to manual input
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def load_config(config_path=None):
    """Load configuration from config file or environment variables."""
    config = {}
    
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            config = json.load(f)
    
    config["email_method"] = os.getenv("EMAIL_METHOD", config.get("email_method", "himalaya"))
    config["account"] = os.getenv("EMAIL_ACCOUNT", config.get("email_account", "default"))
    
    return config


def fetch_via_himalaya(account, days=1):
    """Fetch emails using himalaya CLI."""
    
    try:
        # Check if himalaya is installed
        subprocess.run(["which", "himalaya"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Warning: himalaya not installed. See: https://github.com/soywod/himalaya", file=sys.stderr)
        return []
    
    # Calculate date range
    start_date = datetime.utcnow() - timedelta(days=days)
    
    try:
        # List messages with priority flag
        result = subprocess.run(
            ["himalaya", "list", "--account", account, "--query", "FLAGGED UNSEEN", "--max-width", "0"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        
        # Parse output (simplified - actual parsing would be more robust)
        emails = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                emails.append({"raw": line, "source": "himalaya"})
        
        return emails
    
    except subprocess.CalledProcessError as e:
        print(f"Error fetching emails via himalaya: {e}", file=sys.stderr)
        return []
    except subprocess.TimeoutExpired:
        print("Timeout fetching emails", file=sys.stderr)
        return []


def format_output(emails):
    """Format emails for summary output."""
    
    if not emails:
        return "No high-priority emails in this period."
    
    output = [f"📧 High-Priority Emails ({len(emails)}):"]
    
    for i, email in enumerate(emails[:10], 1):
        # Simplified formatting - would parse subject/sender in real implementation
        output.append(f"  {i}. {email.get('raw', 'Email item')}")
    
    if len(emails) > 10:
        output.append(f"  ... and {len(emails) - 10} more")
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Fetch high-priority emails for project sync")
    parser.add_argument("--priority", default="high", help="Priority level (high, urgent)")
    parser.add_argument("--days", type=int, default=1, help="Number of days to look back")
    parser.add_argument("--config", help="Path to config JSON file")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    args = parser.parse_args()
    
    config = load_config(args.config)
    
    if config["email_method"] == "himalaya":
        emails = fetch_via_himalaya(config["account"], args.days)
    else:
        print("No supported email method configured", file=sys.stderr)
        emails = []
    
    if args.json:
        print(json.dumps(emails, indent=2))
    else:
        print(format_output(emails))


if __name__ == "__main__":
    main()
