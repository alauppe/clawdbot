#!/usr/bin/env python3
"""Motion API CLI - Task and calendar management."""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode

BASE_URL = "https://api.usemotion.com/v1"

def get_api_key():
    """Load API key from config file or environment."""
    # Check environment first
    if key := os.environ.get("MOTION_API_KEY"):
        return key
    
    # Check config file
    config_path = Path.home() / ".config" / "motion" / "credentials"
    if config_path.exists():
        for line in config_path.read_text().strip().split("\n"):
            if line.startswith("MOTION_API_KEY="):
                return line.split("=", 1)[1].strip()
    
    print("Error: No API key found. Set MOTION_API_KEY or create ~/.config/motion/credentials", file=sys.stderr)
    sys.exit(1)

def api_request(method, endpoint, data=None, params=None, max_retries=3):
    """Make API request with retry logic for rate limits."""
    api_key = get_api_key()
    url = f"{BASE_URL}{endpoint}"
    
    if params:
        # Filter None values
        params = {k: v for k, v in params.items() if v is not None}
        if params:
            url += "?" + urlencode(params)
    
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }
    
    body = json.dumps(data).encode() if data else None
    
    for attempt in range(max_retries):
        try:
            req = Request(url, data=body, headers=headers, method=method)
            with urlopen(req) as resp:
                if resp.status == 204:
                    return None
                return json.loads(resp.read().decode())
        except HTTPError as e:
            if e.code == 429:
                # Rate limited - get retry-after header
                retry_after = int(e.headers.get("Retry-After", 60))
                if attempt < max_retries - 1:
                    print(f"Rate limited. Retrying in {retry_after}s...", file=sys.stderr)
                    time.sleep(retry_after)
                    continue
            error_body = e.read().decode() if e.fp else str(e)
            print(f"API Error {e.code}: {error_body}", file=sys.stderr)
            sys.exit(1)
    
    print("Max retries exceeded", file=sys.stderr)
    sys.exit(1)

def format_output(data, format_type="json"):
    """Format output for display."""
    if data is None:
        return
    if format_type == "json":
        print(json.dumps(data, indent=2))
    else:
        print(data)

# ============ TASK COMMANDS ============

def cmd_tasks(args):
    """List tasks."""
    params = {
        "workspaceId": args.workspace,
        "projectId": args.project,
        "status": args.status,
        "assigneeId": args.assignee,
        "label": args.label,
    }
    result = api_request("GET", "/tasks", params=params)
    format_output(result)

def cmd_task(args):
    """Get a single task."""
    result = api_request("GET", f"/tasks/{args.task_id}")
    format_output(result)

def cmd_create(args):
    """Create a task."""
    data = {
        "name": args.name,
        "workspaceId": args.workspace,
    }
    
    if args.due:
        data["dueDate"] = args.due
    if args.duration:
        # Handle special values
        if args.duration.upper() in ("NONE", "REMINDER"):
            data["duration"] = args.duration.upper()
        else:
            data["duration"] = int(args.duration)
    if args.project:
        data["projectId"] = args.project
    if args.description:
        data["description"] = args.description
    if args.priority:
        data["priority"] = args.priority.upper()
    if args.label:
        data["labels"] = [args.label]
    if args.assignee:
        data["assigneeId"] = args.assignee
    if args.deadline:
        data["deadlineType"] = args.deadline.upper()
    if args.start_on:
        data["startOn"] = args.start_on
    if args.auto_schedule:
        data["autoScheduled"] = {
            "startDate": args.start_on or None,
            "deadlineType": (args.deadline or "SOFT").upper(),
            "schedule": "Work Hours",  # Default schedule
        }
    
    result = api_request("POST", "/tasks", data=data)
    format_output(result)

def cmd_update(args):
    """Update a task."""
    data = {}
    
    if args.name:
        data["name"] = args.name
    if args.due:
        data["dueDate"] = args.due
    if args.duration:
        if args.duration.upper() in ("NONE", "REMINDER"):
            data["duration"] = args.duration.upper()
        else:
            data["duration"] = int(args.duration)
    if args.status:
        data["status"] = args.status
    if args.description:
        data["description"] = args.description
    if args.priority:
        data["priority"] = args.priority.upper()
    
    if not data:
        print("Error: No updates specified", file=sys.stderr)
        sys.exit(1)
    
    result = api_request("PATCH", f"/tasks/{args.task_id}", data=data)
    format_output(result)

def cmd_complete(args):
    """Complete a task (set status to Completed)."""
    # Motion uses status name to mark tasks complete
    data = {"status": "Completed"}
    result = api_request("PATCH", f"/tasks/{args.task_id}", data=data)
    format_output(result)

def cmd_delete(args):
    """Delete a task."""
    api_request("DELETE", f"/tasks/{args.task_id}")
    print(f"Task {args.task_id} deleted")

def cmd_move(args):
    """Move a task to a different workspace/project."""
    data = {"workspaceId": args.workspace}
    if args.project:
        data["projectId"] = args.project
    result = api_request("POST", f"/tasks/{args.task_id}/move", data=data)
    format_output(result)

def cmd_unassign(args):
    """Unassign a task."""
    result = api_request("POST", f"/tasks/{args.task_id}/unassign")
    format_output(result)

# ============ RECURRING TASK COMMANDS ============

def cmd_recurring(args):
    """List recurring tasks."""
    params = {"workspaceId": args.workspace}
    result = api_request("GET", "/recurring-tasks", params=params)
    format_output(result)

def cmd_recurring_create(args):
    """Create a recurring task."""
    data = {
        "name": args.name,
        "frequency": args.frequency.lower(),
        "workspaceId": args.workspace,
    }
    
    if args.days:
        # Convert day names to format expected by API
        data["daysOfWeek"] = [d.strip().upper()[:3] for d in args.days.split(",")]
    if args.duration:
        data["duration"] = int(args.duration)
    if args.project:
        data["projectId"] = args.project
    
    result = api_request("POST", "/recurring-tasks", data=data)
    format_output(result)

def cmd_recurring_delete(args):
    """Delete a recurring task."""
    api_request("DELETE", f"/recurring-tasks/{args.task_id}")
    print(f"Recurring task {args.task_id} deleted")

# ============ PROJECT COMMANDS ============

def cmd_projects(args):
    """List projects."""
    params = {"workspaceId": args.workspace}
    result = api_request("GET", "/projects", params=params)
    format_output(result)

def cmd_project(args):
    """Get a project."""
    result = api_request("GET", f"/projects/{args.project_id}")
    format_output(result)

def cmd_project_create(args):
    """Create a project."""
    data = {
        "name": args.name,
        "workspaceId": args.workspace,
    }
    if args.description:
        data["description"] = args.description
    
    result = api_request("POST", "/projects", data=data)
    format_output(result)

# ============ OTHER COMMANDS ============

def cmd_workspaces(args):
    """List workspaces."""
    result = api_request("GET", "/workspaces")
    format_output(result)

def cmd_users(args):
    """List users."""
    params = {"workspaceId": args.workspace}
    result = api_request("GET", "/users", params=params)
    format_output(result)

def cmd_me(args):
    """Get current user."""
    result = api_request("GET", "/users/me")
    format_output(result)

def cmd_schedules(args):
    """Get schedules."""
    params = {"workspaceId": args.workspace}
    result = api_request("GET", "/schedules", params=params)
    format_output(result)

def cmd_statuses(args):
    """Get statuses for a workspace."""
    params = {"workspaceId": args.workspace}
    result = api_request("GET", "/statuses", params=params)
    format_output(result)

def cmd_comments(args):
    """Get comments on a task."""
    params = {"taskId": args.task_id}
    result = api_request("GET", "/comments", params=params)
    format_output(result)

def cmd_comment(args):
    """Add a comment to a task."""
    data = {
        "taskId": args.task_id,
        "content": args.content,
    }
    result = api_request("POST", "/comments", data=data)
    format_output(result)

def main():
    parser = argparse.ArgumentParser(description="Motion API CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # tasks
    p = subparsers.add_parser("tasks", help="List tasks")
    p.add_argument("--workspace", "-w", help="Workspace ID")
    p.add_argument("--project", "-p", help="Project ID")
    p.add_argument("--status", "-s", help="Status filter")
    p.add_argument("--assignee", "-a", help="Assignee ID")
    p.add_argument("--label", "-l", help="Label filter")
    p.set_defaults(func=cmd_tasks)
    
    # task
    p = subparsers.add_parser("task", help="Get a task")
    p.add_argument("task_id", help="Task ID")
    p.set_defaults(func=cmd_task)
    
    # create
    p = subparsers.add_parser("create", help="Create a task")
    p.add_argument("name", help="Task name")
    p.add_argument("--due", "-d", help="Due date (ISO 8601)")
    p.add_argument("--duration", help="Duration in minutes, NONE, or REMINDER")
    p.add_argument("--project", "-p", help="Project ID")
    p.add_argument("--workspace", "-w", help="Workspace ID")
    p.add_argument("--description", help="Task description")
    p.add_argument("--priority", choices=["asap", "high", "medium", "low"], help="Priority")
    p.add_argument("--label", "-l", help="Label")
    p.add_argument("--assignee", "-a", help="Assignee ID")
    p.add_argument("--deadline", choices=["hard", "soft", "none"], help="Deadline type")
    p.add_argument("--start-on", help="Start date (YYYY-MM-DD)")
    p.add_argument("--auto-schedule", action="store_true", help="Enable auto-scheduling")
    p.set_defaults(func=cmd_create)
    
    # update
    p = subparsers.add_parser("update", help="Update a task")
    p.add_argument("task_id", help="Task ID")
    p.add_argument("--name", "-n", help="New name")
    p.add_argument("--due", "-d", help="Due date (ISO 8601)")
    p.add_argument("--duration", help="Duration in minutes, NONE, or REMINDER")
    p.add_argument("--status", "-s", help="Status")
    p.add_argument("--description", help="Description")
    p.add_argument("--priority", choices=["asap", "high", "medium", "low"], help="Priority")
    p.set_defaults(func=cmd_update)
    
    # complete
    p = subparsers.add_parser("complete", help="Complete a task")
    p.add_argument("task_id", help="Task ID")
    p.set_defaults(func=cmd_complete)
    
    # delete
    p = subparsers.add_parser("delete", help="Delete a task")
    p.add_argument("task_id", help="Task ID")
    p.set_defaults(func=cmd_delete)
    
    # move
    p = subparsers.add_parser("move", help="Move a task")
    p.add_argument("task_id", help="Task ID")
    p.add_argument("--workspace", "-w", required=True, help="Target workspace ID")
    p.add_argument("--project", "-p", help="Target project ID")
    p.set_defaults(func=cmd_move)
    
    # unassign
    p = subparsers.add_parser("unassign", help="Unassign a task")
    p.add_argument("task_id", help="Task ID")
    p.set_defaults(func=cmd_unassign)
    
    # recurring
    p = subparsers.add_parser("recurring", help="List recurring tasks")
    p.add_argument("--workspace", "-w", help="Workspace ID")
    p.set_defaults(func=cmd_recurring)
    
    # recurring-create
    p = subparsers.add_parser("recurring-create", help="Create recurring task")
    p.add_argument("name", help="Task name")
    p.add_argument("--frequency", "-f", required=True, choices=["daily", "weekly", "monthly"], help="Frequency")
    p.add_argument("--days", help="Days of week (e.g., mon,tue,wed)")
    p.add_argument("--duration", help="Duration in minutes")
    p.add_argument("--project", "-p", help="Project ID")
    p.add_argument("--workspace", "-w", help="Workspace ID")
    p.set_defaults(func=cmd_recurring_create)
    
    # recurring-delete
    p = subparsers.add_parser("recurring-delete", help="Delete recurring task")
    p.add_argument("task_id", help="Recurring task ID")
    p.set_defaults(func=cmd_recurring_delete)
    
    # projects
    p = subparsers.add_parser("projects", help="List projects")
    p.add_argument("--workspace", "-w", help="Workspace ID")
    p.set_defaults(func=cmd_projects)
    
    # project
    p = subparsers.add_parser("project", help="Get a project")
    p.add_argument("project_id", help="Project ID")
    p.set_defaults(func=cmd_project)
    
    # project-create
    p = subparsers.add_parser("project-create", help="Create a project")
    p.add_argument("name", help="Project name")
    p.add_argument("--workspace", "-w", required=True, help="Workspace ID")
    p.add_argument("--description", help="Project description")
    p.set_defaults(func=cmd_project_create)
    
    # workspaces
    p = subparsers.add_parser("workspaces", help="List workspaces")
    p.set_defaults(func=cmd_workspaces)
    
    # users
    p = subparsers.add_parser("users", help="List users")
    p.add_argument("--workspace", "-w", help="Workspace ID")
    p.set_defaults(func=cmd_users)
    
    # me
    p = subparsers.add_parser("me", help="Get current user")
    p.set_defaults(func=cmd_me)
    
    # schedules
    p = subparsers.add_parser("schedules", help="Get schedules")
    p.add_argument("--workspace", "-w", help="Workspace ID")
    p.set_defaults(func=cmd_schedules)
    
    # statuses
    p = subparsers.add_parser("statuses", help="Get statuses")
    p.add_argument("--workspace", "-w", required=True, help="Workspace ID")
    p.set_defaults(func=cmd_statuses)
    
    # comments
    p = subparsers.add_parser("comments", help="Get comments on a task")
    p.add_argument("task_id", help="Task ID")
    p.set_defaults(func=cmd_comments)
    
    # comment
    p = subparsers.add_parser("comment", help="Add a comment")
    p.add_argument("task_id", help="Task ID")
    p.add_argument("content", help="Comment text")
    p.set_defaults(func=cmd_comment)
    
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
