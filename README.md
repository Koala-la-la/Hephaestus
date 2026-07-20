# EDE — Engineering Discipline Enforcer

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-73%20passed-brightgreen.svg)](tests/) [![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](CHANGELOG.md)

**EDE** is a CLI tool that enforces engineering discipline throughout the full-stack development lifecycle. Unlike general-purpose AI agents that can be "persuaded" to skip steps, EDE implements **hard-constraint pipelines** — you cannot merge code without passing through spec → design → plan → code → test → review → merge.

> "EDE isn't about writing code faster. It's about ensuring the code you write went through the right process."

## Why EDE?

General-purpose AI agents (CodeWhale, Claude Code, Codex) operate on **conversation-driven harnesses** — all constraints are soft prompts that the model can bypass. EDE operates on a **process-driven harness** — constraints are hard-coded gates.

| | General AI Agents | EDE |
|---|---|---|
| Spec enforcement | "Please follow the spec" (soft) | Gate check — blocked if no spec |
| Test gate | Agent claims "tests pass" | Actually runs `pytest` |
| Human checkpoints | Can be skipped | System-level blocking state |
| Change visibility | Raw diff | Summary + intent groups + risk labels |
| Error memory | Lost between sessions | Auto-written to `context.yaml` |
| Cost efficiency | GPT-4 rates | DeepSeek-optimized (prefix cache, thinking budget) |

## Quick Start

```bash
# Install
pip install ede

# Set your API key (never share this!)
export DEEPSEEK_API_KEY="sk-xxx"

# Optional: relay / custom model
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
export DEEPSEEK_MODEL="deepseek-chat"

# Initialize a project
cd your-project
ede init "My Awesome Project"

# Create and run a task
ede task create "Add user authentication with JWT"
ede task run          # spec → design → plan (human checkpoints)
ede confirm spec      # Confirm the spec
ede confirm design    # Confirm the design
ede confirm plan      # Confirm the plan
ede task run          # code → test → review → merge (auto)

# View dashboard
ede dashboard
```

## Pipeline

```
spec → design → plan → code → test → review → merge
  ✅       ✅       ✅      ✅      ✅       ✅       ✅
```

| Phase | AI Role | Human Role |
|-------|---------|------------|
| spec | Guided requirements clarification | Confirm scope |
| design | Architecture suggestions | Confirm approach |
| plan | Declarative change plan | Confirm steps |
| code | Generate code + change summary | Review high-risk changes |
| test | Generate + run tests | Review coverage gaps |
| review | 3-parallel reviewer agents | Review findings |
| merge | Auto-merge to main | (L4 confirmation) |

## Features

### Hard Constraints, Not Prompts

- **L1/L2/L3 Gates**: lint (auto-fix 2x), test (auto-fix 1x), coverage (human must decide)
- **Human Checkpoints**: spec/design/plan cannot proceed without explicit user confirmation
- **Audit Trail**: every bypass leaves an immutable log

### Change Visibility (FR-003)

Every code change produces:
```
## Change Summary
[What was changed, why, and how]

## Intent Groups
- interface: [API/signature changes]
- logic: [business logic changes]
- test: [test additions]
- refactor: [structural changes]

## Risk Assessment
- low: [safe changes]
- medium: [multi-module changes]
- high: [core logic — MUST REVIEW]
```

### DeepSeek-Optimized

- Prefix cache: stable Constitution in prompt prefix layer (90% cost savings on cache hits)
- Thinking budget: automatic per-phase selection (spec→low, code→high, merge→off)
- Chinese-native prompt optimization

### Self-Refinement

Corrected mistakes don't repeat. After each task, run `ede refine` to automatically update `context.yaml` with learned constraints.

## Architecture

```
CLI (Typer) → Stage Engine (7-phase pipeline)
                ├── Gate Engine (L1/L2/L3)
                ├── Context Engine (project conventions)
                ├── LLM Adapter (DeepSeekProvider)
                ├── Change Visibility (summary parsing)
                ├── Reviewer Orchestrator (3-way parallel)
                └── Self-Refinement (error → update)
```

## Contributing

```bash
git clone https://github.com/your-username/ede.git
cd ede
pip install -e ".[dev]"
pytest tests/ -q
```

## License

MIT
