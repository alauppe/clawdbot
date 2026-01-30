---
name: opus-delegate
description: Delegate complex tasks to Claude Opus 4.5 via Claude CLI. Use when you need Opus-level reasoning for skill building, planning, code review, or complex analysis while running on a lighter model. Invoke for tasks requiring deep reasoning, multi-step planning, or high-stakes decisions.
metadata: {"clawdbot":{"emoji":"🧠","requires":{"bins":["claude","python3"]}}}
---

# Opus Delegate

Delegate complex sub-tasks to Claude Opus 4.5 via the Claude CLI, even when the main conversation uses a different model.

## When to Use

- **Skill building** — designing new skills with proper structure
- **Complex planning** — multi-step workflows, architecture decisions
- **Code review** — thorough analysis of PRs or codebases
- **High-stakes decisions** — anything where you want Opus-level reasoning
- **Research synthesis** — combining multiple sources into coherent output

## Quick Start

```bash
# Simple delegation
~/clawdbot/skills/opus-delegate/scripts/delegate.py "Design a skill for managing Kubernetes deployments"

# With custom system prompt
~/clawdbot/skills/opus-delegate/scripts/delegate.py --system "You are a senior architect" "Review this API design"

# JSON output for parsing
~/clawdbot/skills/opus-delegate/scripts/delegate.py --json "Analyze this code and return {issues: [], suggestions: []}"

# With working directory (for file access)
~/clawdbot/skills/opus-delegate/scripts/delegate.py --workdir ~/project "Review the code in src/"
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--model` | `opus` | Model alias or full name |
| `--workdir` | temp dir | Working directory for file access |
| `--budget` | `5.00` | Max USD to spend |
| `--json` | off | Output as JSON |
| `--system` | none | Custom system prompt |
| `--timeout` | `300` | Timeout in seconds |
| `--quiet` | off | Suppress status messages |

## Integration Patterns

### From Another Skill

```bash
# In your skill's workflow, delegate the complex part
DESIGN=$(~/clawdbot/skills/opus-delegate/scripts/delegate.py --quiet \
  "Design the file structure for a $SKILL_NAME skill that does: $DESCRIPTION")
echo "$DESIGN"
```

### Background Delegation

```bash
# For long-running tasks, use background mode
bash background:true command:"~/clawdbot/skills/opus-delegate/scripts/delegate.py --timeout 600 'Complex analysis task'"
# Returns sessionId for monitoring
process action:log sessionId:XXX
```

### Structured Output

```bash
# Get JSON for programmatic use
RESULT=$(~/clawdbot/skills/opus-delegate/scripts/delegate.py --json \
  "Analyze and return: {\"score\": number, \"issues\": string[], \"recommendation\": string}")
echo "$RESULT" | jq '.score'
```

### With File Context

```bash
# Point to a directory so Opus can read files
~/clawdbot/skills/opus-delegate/scripts/delegate.py \
  --workdir ~/project \
  "Review the architecture in docs/ARCHITECTURE.md and suggest improvements"
```

## Model Aliases

The Claude CLI supports these aliases:
- `opus` — Claude Opus 4.5 (default, best reasoning)
- `sonnet` — Claude Sonnet 4 (faster, still capable)
- Or use full model names like `claude-opus-4-5-20250514`

## Cost Control

Default budget is $5 per delegation. Adjust with `--budget`:

```bash
# Limit to $1 for simple tasks
~/clawdbot/skills/opus-delegate/scripts/delegate.py --budget 1.00 "Quick question"

# Allow more for complex work
~/clawdbot/skills/opus-delegate/scripts/delegate.py --budget 10.00 "Comprehensive codebase review"
```

## Example: Skill Builder Integration

When building skills, delegate the design phase to Opus:

```bash
# 1. Gather requirements (can be done by any model)
REQUIREMENTS="User wants a skill for managing Docker containers..."

# 2. Delegate architecture to Opus
DESIGN=$(~/clawdbot/skills/opus-delegate/scripts/delegate.py --quiet \
  "Design an AgentSkill for: $REQUIREMENTS

Return a complete skill structure including:
- SKILL.md content with proper frontmatter
- Any scripts needed (with full implementation)
- Reference files if applicable

Follow the skill-creator patterns.")

# 3. Create the skill files based on Opus's design
echo "$DESIGN"
```

## Tips

1. **Be specific** — Opus works better with clear, detailed prompts
2. **Use --workdir** — Give file access when the task involves code
3. **Set --timeout** — Increase for complex tasks (default 5 min)
4. **Parse JSON** — Use `--json` + `jq` for structured workflows
5. **Budget wisely** — Opus is expensive; set appropriate limits
