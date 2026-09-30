#!/usr/bin/env python3
"""
Fetch Linear issues and updates for a previous employer workspace.
Usage: python3 fetch_linear.py --days <N> [--config <path>]
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
    
    # Try to load from config file
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            config = json.load(f)
    
    # Override with environment variables if present
    config["api_token"] = os.getenv("LINEAR_API_TOKEN", config.get("linear_api_token"))
    config["workspace_id"] = os.getenv("LINEAR_WORKSPACE_ID", config.get("linear_workspace_id", "former-employer"))
    
    if not config.get("api_token"):
        print("Error: LINEAR_API_TOKEN not found in config or environment", file=sys.stderr)
        sys.exit(1)
    
    return config


def fetch_linear_issues(api_token, days=1):
    """Fetch Linear issues from the past N days."""
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # GraphQL query for Linear API
    query = """
    query Issues($filter: IssueFilter) {
      issues(filter: $filter, first: 100) {
        nodes {
          id
          title
          description
          state {
            name
            type
          }
          priority
          priorityLabel
          assignee {
            name
            email
          }
          createdAt
          updatedAt
          completedAt
          project {
            name
          }
          labels {
            nodes {
              name
            }
          }
          url
        }
      }
    }
    """
    
    variables = {
        "filter": {
            "updatedAt": {
                "gte": start_date.isoformat()
            }
        }
    }
    
    headers = {
        "Authorization": api_token,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            "https://api.linear.app/graphql",
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}", file=sys.stderr)
            return []
        
        return data.get("data", {}).get("issues", {}).get("nodes", [])
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Linear data: {e}", file=sys.stderr)
        return []


def format_output(issues):
    """Format issues for summary output."""
    
    if not issues:
        return "No Linear updates in this period."
    
    # Categorize issues
    completed = [i for i in issues if i.get("completedAt")]
    high_priority = [i for i in issues if i.get("priority", 0) >= 3]
    blockers = [i for i in issues if any(
        label.get("name", "").lower() == "blocker" 
        for label in i.get("labels", {}).get("nodes", [])
    )]
    
    output = []
    
    # Completed items
    if completed:
        output.append(f"✅ Completed ({len(completed)}):")
        for issue in completed[:5]:  # Top 5
            output.append(f"  - {issue['title']} ({issue.get('state', {}).get('name', 'Done')})")
    
    # High priority items
    if high_priority:
        output.append(f"\n🔥 High Priority ({len(high_priority)}):")
        for issue in high_priority[:5]:
            priority = issue.get("priorityLabel", "High")
            output.append(f"  - [{priority}] {issue['title']}")
    
    # Blockers
    if blockers:
        output.append(f"\n🚨 Blockers ({len(blockers)}):")
        for issue in blockers[:3]:
            output.append(f"  - {issue['title']}")
    
    # Summary stats
    output.append(f"\n📊 Stats:")
    output.append(f"  - Total updates: {len(issues)}")
    output.append(f"  - Completed: {len(completed)}")
    output.append(f"  - In progress: {len([i for i in issues if i.get('state', {}).get('type') == 'started'])}")
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Fetch Linear issues for project sync")
    parser.add_argument("--days", type=int, default=1, help="Number of days to look back")
    parser.add_argument("--config", help="Path to config JSON file")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    args = parser.parse_args()
    
    config = load_config(args.config)
    issues = fetch_linear_issues(config["api_token"], args.days)
    
    if args.json:
        print(json.dumps(issues, indent=2))
    else:
        print(format_output(issues))


if __name__ == "__main__":
    main()
