---
name: motion
description: Motion task/calendar management API. Use when creating, listing, updating, or completing tasks in Motion (usemotion.com). Also handles projects, workspaces, recurring tasks, schedules, comments, and custom fields.
---

# Motion API Skill

CLI wrapper for the Motion REST API (task/calendar management).

## Setup

Store your API key:
```bash
echo "MOTION_API_KEY=your_key_here" > ~/.config/motion/credentials
```

Get your API key from: Settings → API (in Motion app)

## CLI Usage

```bash
motion <command> [options]
```

### Tasks

```bash
# List tasks
motion tasks [--workspace ID] [--project ID] [--status STATUS] [--assignee ID] [--label LABEL]

# Get a task
motion task <task_id>

# Create a task
motion create "Task name" [--due DATE] [--duration MINS] [--project ID] [--workspace ID] \
  [--description TEXT] [--priority PRIORITY] [--label LABEL] [--assignee ID] \
  [--auto-schedule] [--deadline hard|soft|none] [--start-on DATE]

# Update a task
motion update <task_id> [--name TEXT] [--due DATE] [--duration MINS] [--status STATUS] \
  [--description TEXT] [--priority PRIORITY]

# Complete a task
motion complete <task_id>

# Delete a task
motion delete <task_id>

# Move a task to different workspace/project
motion move <task_id> --workspace ID [--project ID]

# Unassign a task
motion unassign <task_id>
```

### Recurring Tasks

```bash
# List recurring tasks
motion recurring [--workspace ID]

# Create recurring task
motion recurring-create "Task name" --frequency daily|weekly|monthly \
  [--days mon,tue,wed] [--duration MINS] [--project ID] [--workspace ID]

# Delete recurring task
motion recurring-delete <task_id>
```

### Projects

```bash
# List projects
motion projects [--workspace ID]

# Get a project
motion project <project_id>

# Create a project
motion project-create "Project name" --workspace ID [--description TEXT]
```

### Other

```bash
# List workspaces
motion workspaces

# List users
motion users [--workspace ID]

# Get current user
motion me

# Get schedules
motion schedules [--workspace ID]

# Get statuses for a workspace
motion statuses --workspace ID

# Comments
motion comments <task_id>
motion comment <task_id> "Comment text"
```

## Date Formats

- Due dates: ISO 8601 format (e.g., `2026-01-25T14:00:00Z` or `2026-01-25`)
- Start dates: `YYYY-MM-DD` format
- Duration: Minutes as integer, or `NONE`, or `REMINDER`

## Task Fields Reference

- **duration**: Minutes (int), "NONE", or "REMINDER"
- **deadlineType**: "HARD", "SOFT" (default), or "NONE"
- **autoScheduled**: Enable Motion's AI scheduling with `--auto-schedule`
- **priority**: "ASAP", "HIGH", "MEDIUM", "LOW"
- **status**: Workspace-specific status name

## Examples

```bash
# Create a 30-min task due tomorrow, auto-scheduled
motion create "Review PR" --due 2026-01-22T17:00:00Z --duration 30 --auto-schedule

# Create a recurring daily standup
motion recurring-create "Daily standup" --frequency daily --duration 15 --days mon,tue,wed,thu,fri

# List incomplete tasks in a project
motion tasks --project proj_abc123 --status "To Do"

# Complete a task
motion complete task_xyz789
```

## Rate Limits

Motion API has rate limits. The CLI handles 429 responses with automatic retry after the specified delay.

## API Reference

Base URL: `https://api.usemotion.com/v1`
Auth: `X-API-Key` header

Full docs: https://docs.usemotion.com
