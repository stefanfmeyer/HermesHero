#!/usr/bin/env python3
"""
Fetch Slack messages from a previous employer workspace (read-only).
Usage: python3 fetch_slack.py --workspace former-employer --days <N> [--config <path>]

IMPORTANT: This is READ-ONLY. Never send messages to this workspace.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests module not installed. Run: pip3 install requests", file=sys.stderr)
    sys.exit(1)


def load_config(config_path=None):
    """Load configuration from config file or environment variables."""
    config = {}
    
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            config = json.load(f)
    
    config["slack_token"] = os.getenv("SLACK_USER_TOKEN", config.get("slack_user_token"))
    config["channels"] = config.get("slack_channels", ["general", "operations"])
    
    if not config.get("slack_token"):
        print("Error: SLACK_USER_TOKEN not found in config or environment", file=sys.stderr)
        sys.exit(1)
    
    return config


def fetch_slack_messages(token, channels, days=1):
    """Fetch recent messages from specified Slack channels."""
    
    # Calculate oldest timestamp
    oldest = (datetime.utcnow() - timedelta(days=days)).timestamp()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    all_messages = []
    
    for channel in channels:
        try:
            # Get channel ID if name provided
            if not channel.startswith("C"):
                # List conversations to find channel ID
                conv_response = requests.get(
                    "https://slack.com/api/conversations.list",
                    headers=headers,
                    params={"types": "public_channel,private_channel"},
                    timeout=30
                )
                conv_data = conv_response.json()
                
                if not conv_data.get("ok"):
                    print(f"Error listing channels: {conv_data.get('error')}", file=sys.stderr)
                    continue
                
                # Find channel by name
                channel_obj = next(
                    (c for c in conv_data.get("channels", []) if c.get("name") == channel),
                    None
                )
                
                if not channel_obj:
                    print(f"Channel '{channel}' not found", file=sys.stderr)
                    continue
                
                channel_id = channel_obj["id"]
            else:
                channel_id = channel
            
            # Fetch conversation history
            response = requests.get(
                "https://slack.com/api/conversations.history",
                headers=headers,
                params={
                    "channel": channel_id,
                    "oldest": oldest,
                    "limit": 100
                },
                timeout=30
            )
            
            data = response.json()
            
            if not data.get("ok"):
                print(f"Error fetching messages from {channel}: {data.get('error')}", file=sys.stderr)
                continue
            
            messages = data.get("messages", [])
            
            # Filter for important messages (threads, reactions, mentions)
            important = [
                m for m in messages
                if m.get("thread_ts") or m.get("reactions") or "@channel" in m.get("text", "")
            ]
            
            all_messages.extend([{
                "channel": channel,
                "text": m.get("text", ""),
                "user": m.get("user", "unknown"),
                "ts": m.get("ts"),
                "thread": bool(m.get("thread_ts")),
                "reactions": len(m.get("reactions", []))
            } for m in important])
        
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Slack data for {channel}: {e}", file=sys.stderr)
            continue
    
    return all_messages


def format_output(messages):
    """Format messages for summary output."""
    
    if not messages:
        return "No significant Slack activity in this period."
    
    output = [f"💬 Slack Activity ({len(messages)} important messages):"]
    
    # Group by channel
    by_channel = {}
    for msg in messages:
        channel = msg["channel"]
        if channel not in by_channel:
            by_channel[channel] = []
        by_channel[channel].append(msg)
    
    for channel, msgs in by_channel.items():
        output.append(f"\n  #{channel} ({len(msgs)} messages):")
        for msg in msgs[:3]:  # Top 3 per channel
            preview = msg["text"][:80] + "..." if len(msg["text"]) > 80 else msg["text"]
            indicators = []
            if msg["thread"]:
                indicators.append("🧵 thread")
            if msg["reactions"] > 0:
                indicators.append(f"👍 {msg['reactions']}")
            
            ind_str = f" [{', '.join(indicators)}]" if indicators else ""
            output.append(f"    - {preview}{ind_str}")
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Fetch Slack messages for project sync (READ-ONLY)")
    parser.add_argument("--workspace", default="former-employer", help="Workspace name")
    parser.add_argument("--days", type=int, default=1, help="Number of days to look back")
    parser.add_argument("--config", help="Path to config JSON file")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    args = parser.parse_args()
    
    config = load_config(args.config)
    messages = fetch_slack_messages(config["slack_token"], config["channels"], args.days)
    
    if args.json:
        print(json.dumps(messages, indent=2))
    else:
        print(format_output(messages))


if __name__ == "__main__":
    main()
