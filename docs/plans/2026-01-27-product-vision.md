---
id: ivan-task-manager-product-vision
title: Ivan Task Manager - Product Vision
type: project
status: active
owner: ivan
created: 2026-01-27
updated: 2026-01-28
tags: [vision, product, strategy, roadmap]
---

# Ivan Task Manager — Product Vision

**The Blueprint for Ivan's AI Chief of Staff**

Version: 1.1
Created: 2026-01-27
Updated: 2026-01-28
Status: Living Document
Owner: Ivan

---

## What This Document Is

This is the **product vision** for ivan-task-manager — not just a task aggregator, but the foundation for an AI Chief of Staff that acts as Ivan.

Read this document:
- Before starting any development session
- When deciding what to build next
- When tempted to "improve" without understanding the bigger picture
- When context is lost between sessions

This document captures the WHAT and WHY. Implementation details live elsewhere.

---

## Part I: The Problem

### The Situation

Ivan is a CEO with:
- Multiple companies (Markster, others)
- Multiple countries and continents
- Multiple roles (CEO, board member, investor)
- Multiple domains (sales, legal, accounting, technical, marketing)
- ~20,000 contacts in the rolodex
- Constant context-switching between tasks, people, and priorities

### The Core Pain

**Context-switching is killing productivity.**

Tasks exist in isolation across systems (ClickUp, GitHub, email, WhatsApp, Slack, meeting transcripts). Each task looks like a standalone item, but they're actually part of larger intentions with people, deadlines, and money attached.

Without context:
- Tasks show "No deadline" when the project has a hard date
- Priority is wrong because the system doesn't know who's affected
- Ivan spends all day pushing documents between places instead of doing high-leverage work
- Things fall through cracks because nothing connects the dots

### The Vision

**An integration layer between Ivan and the outside world that:**

1. **Collects** — Captures everything from all channels
2. **Collates** — Organizes by entity (person/company) and project
3. **Analyzes** — Understands context, deadlines, relationships
4. **Prioritizes** — Surfaces what matters NOW
5. **Executes** — Agents handle repeatable work (draft mode → auto mode)
6. **Learns** — Gets smarter over time through feedback loops

The system acts as Ivan — not replacing judgment, but handling the outer loop so Ivan can focus on high-leverage decisions.

---

## Part II: Principles

These come from the Agent System Bible and this design process.

### Principle 1: Entity-Centric, Not Task-Centric

Everything connects to an **entity** (person or company). Tasks are just actions within the context of an entity relationship.

"Send proposal to Mark" is meaningless without knowing: Who is Mark? What's our intention? What's the deadline? What's at stake?

### Principle 2: Intention Drives Priority

Every entity relationship has an **intention**:
- Mark → Showcase client → Channel partner → Revenue
- Kyle → Discovery → Potential deal → Expansion
- YC → Application → Funding

Tasks inherit urgency from the intention's timeline, not just their own due date.

### Principle 3: Unknown Variables Are Normal

Not everything has a deal value. Not everything has a deadline. Networking, events, and relationship-building have uncertain outcomes.

The system must handle ambiguity gracefully — capturing context even when outcomes are unknown.

### Principle 4: Research Everything, Decide Once

Every contact needs research. Every opportunity needs cataloguing. Decisions should be captured so they don't need to be re-made.

The system accumulates knowledge over time, reducing repeated work.

### Principle 5: Workflows, Not Code

Repeatable processes are documented as **workflows** — step-by-step procedures that any agent (Codex, Claude, human) can follow.

Workflows are the unit of automation. Code implements workflows, not the other way around.

### Principle 6: Modular and Consistent

Different agents (Codex instances, Claude sessions) work on different pieces, but they all:
- Read from the same context
- Follow the same conventions (Attila's standards)
- Output in compatible formats
- Serve the same product

### Principle 7: Work Now, Scale Later

The system must be useful TODAY with 9 tasks, while being designed to handle 1,000+ tasks and 20,000 contacts.

Don't over-engineer for scale. Don't under-design for it either.

### Principle 8: Draft Mode Before Auto Mode

External-facing actions (emails, messages, posts) require human approval until trust is earned.

Autonomy increases gradually based on rejection rate and confidence.

### Principle 9: Context Survives Sessions

Claude/Codex sessions end. Context is lost. Everything important must be captured in files that persist:
- Design docs (like this one)
- Entity context folders
- Decision logs
- Workflow definitions

### Principle 10: Compound, Don't Reset

The system gets smarter over time. Metrics feed back. Research accumulates. Don't start over — build on what exists.

---

## Part III: The Layered Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 4: EXECUTION                                              │
│ Agents do work: drafts, research, analysis, follow-ups          │
│ Tech: Codex, Claude, Azure OpenAI, Make.com                     │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 3: PRIORITIZATION                                         │
│ What needs attention NOW? Scoring, urgency, blocking            │
│ Tech: ivan-task-manager (this repo)                             │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2: CONTEXT                                                │
│ Entity profiles, project state, relationship history            │
│ Tech: GitHub folders, Google Docs, vector DB (future)           │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: CAPTURE                                                │
│ Raw inputs from all channels                                    │
│ Tech: Gmail API, Slack API, Fireflies, ClickUp, GitHub          │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 1: Capture (Sources)

**What:** Raw data from everywhere Ivan operates.

**Sources:**
- Email (Gmail)
- Chat (Slack, WhatsApp, LinkedIn DMs, Twitter DMs, Facebook)
- Meetings (Zoom/Google Meet transcripts via Fireflies)
- Tasks (ClickUp, GitHub Issues)
- Documents (Google Docs, Notion)
- Calendar (Google Calendar)
- CRM (HubSpot)
- Phone calls (transcribed)

**Output:** Raw data with metadata (source, timestamp, participants).

**Current State:** Partially implemented (Gmail, Slack, ClickUp, GitHub plugins exist).

### Layer 2: Context (Entity + Project)

**What:** Organized knowledge about entities and their projects.

**Entity:** A person or company Ivan has a relationship with.

```yaml
entity:
  id: "mark-smith-ai-branding"
  type: person  # or company
  name: "Mark Smith"
  company: "AI Branding Academy"

  intention: "Showcase client → Channel partner → Revenue multiplier"

  workstreams:
    - id: "mark-system-setup"
      name: "System Setup on Markster"
      status: overdue
      deadline: 2026-01-25

    - id: "mark-workshop"
      name: "Workshop Success"
      status: active
      deadline: 2026-02-15
      milestone: "Workshop date"
      revenue_potential: "$10,000+"

    - id: "mark-channel-assets"
      name: "Channel Partner Assets"
      status: planned
      depends_on: ["mark-workshop"]

    - id: "mark-relationship"
      name: "Ongoing Relationship"
      status: active
      type: nurture
      # No deadline - ongoing

  channels:  # Where context lives
    - type: github
      ref: "markster-exec/project-tracker#16"
    - type: clickup
      ref: "869bxxuwr"
    - type: gdoc
      ref: "1byTVcZUJ7RXSOWTlYhJ7pQiARarBNNUB_adjXIuSnv8"
    - type: email
      thread_ids: ["..."]
    - type: slack
      channel: "#mark-ai-branding"

  contacts:
    - name: "Mark Smith"
      email: "mark@example.com"
      linkedin: "..."

  context_summary: |
    Mark is building AI Branding Academy. We're setting up his system
    on Markster as a showcase. Success here = case study + channel partner.
    Workshop in mid-Feb is the key milestone.

  last_touch: 2026-01-25
  next_action: "Complete system setup (overdue)"
```

**Project/Workstream:** A specific initiative within an entity relationship.

Projects have:
- Deadline (explicit or inherited from milestone)
- Status (planned, active, blocked, complete)
- Revenue potential (known or unknown)
- Dependencies (other projects that must complete first)
- Tasks (from ClickUp, GitHub, etc.)

**Output:** Structured entity profiles that any agent can read.

**Current State:** NOT implemented. This is the key gap.

### Layer 3: Prioritization (Ivan Task Manager)

**What:** Scoring and surfacing what needs attention.

**Current Scoring:**
```
Score = (Revenue × 1000) + (Blocking × 500 × count) + (Urgency × 100) + Recency
```

**Enhanced Scoring (with context):**
```
Score = (Revenue × 1000)
      + (Blocking × 500 × count)
      + (Urgency × 100)              # Task deadline
      + (Project Urgency × 50)       # Project/workstream deadline
      + (Entity Priority × 25)       # How important is this relationship?
      + (Recency × 1)
```

Tasks inherit urgency from their project and entity.

**Output:** Ranked task list with full context.

**Current State:** Basic scoring implemented. Entity/project awareness NOT implemented.

### Layer 4: Execution (Agents)

**What:** Agents that do work following defined workflows.

**Agent Types:**
| Agent | Purpose | Autonomy |
|-------|---------|----------|
| Researcher | Enrich entities with context | Full auto |
| Scorer | Prioritize and rank | Full auto |
| Drafter | Create messages, docs | Draft only (human approves) |
| Executor | Send messages, update systems | Human triggered |
| Tracker | Update metrics, surface insights | Full auto |
| Chief of Staff | Daily brief, recommendations | Full auto |

**How Agents Work:**
1. Read entity context + task
2. Follow workflow template
3. Produce structured output
4. Human approves (if external-facing)
5. System updates

**Output:** Work products (drafts, research, analysis).

**Current State:** NOT implemented. Future phase.

---

## Part IV: Workflows

Workflows are documented procedures that agents follow. They're the unit of automation.

### Workflow: Entity Onboarding

**Trigger:** New entity identified (from meeting, email, event).

**Steps:**
1. Create entity profile (YAML or folder)
2. Capture all existing context (search emails, transcripts, docs)
3. Research: LinkedIn, company website, news
4. Extract: intentions, commitments, deadlines, open questions
5. Generate tasks: What needs to happen?
6. Assign deadlines: Based on commitments or entity priority
7. Notify: Slack summary

**Output:** Complete entity profile + initial tasks.

### Workflow: Transcript Processing

**Trigger:** New meeting transcript (from Fireflies).

**Steps:**
1. Identify participants → map to entities
2. Extract: decisions, action items, commitments, deadlines
3. Update entity profiles with new context
4. Create tasks with owners and deadlines
5. Flag: anything needing immediate attention

**Output:** Tasks created, entity context updated.

### Workflow: Relationship Nurturing

**Trigger:** Scheduled (weekly) or event (birthday, job change, post).

**Steps:**
1. Scan entity list for nurture opportunities
2. Check: recent activity, special dates, social signals
3. Draft: personalized touchpoint (comment, DM, email)
4. Queue for approval
5. Track: engagement, response

**Output:** Nurture actions queued.

### Workflow: Daily Brief (Chief of Staff)

**Trigger:** Daily at 7:00 AM.

**Steps:**
1. Scan all tasks by priority
2. Check: overdue, due today, blocking others
3. Check: entity deadlines approaching
4. Generate: Top 3 focus items with context
5. Generate: Don't-do list (what to skip today)
6. Generate: One decision needed
7. Post to Slack

**Output:** Daily brief in Slack + ivan morning command.

### Workflow: Weekly Review

**Trigger:** Weekly (Sunday evening).

**Steps:**
1. Review: tasks completed, tasks added, tasks overdue
2. Review: entity progress (who moved forward, who stalled)
3. Review: metrics (response rates, deal progress)
4. Surface: stuck items, neglected entities
5. Recommend: priority adjustments

**Output:** Weekly summary + recommendations.

---

## Part V: Technology Mapping

How existing tools serve each layer.

| Layer | Component | Technology | Status |
|-------|-----------|------------|--------|
| Capture | Email | Gmail API (gmail_manager.rb) | ✅ Built |
| Capture | Chat | Slack API (slack_manager.rb) | ✅ Built |
| Capture | Tasks | ClickUp API (clickup_manager.rb) | ✅ Built |
| Capture | Tasks | GitHub API (gh CLI) | ✅ Built |
| Capture | Meetings | Fireflies API | ❌ Not built |
| Capture | WhatsApp | Manual or API | ❌ Not built |
| Capture | Calendar | Google Calendar API | ❌ Not built |
| Context | Entity store | GitHub folders or YAML | ❌ Not built |
| Context | Vector search | Azure AI Search (future) | ❌ Not built |
| Prioritization | Scoring | ivan-task-manager | ✅ Complete |
| Prioritization | Slack Bot | ivan-task-manager (bot.py) | ✅ Complete |
| Prioritization | Error handling | ivan-task-manager (syncer.py) | ✅ Complete |
| Prioritization | Entity-aware | ivan-task-manager | ❌ Not built |
| Execution | Research | Codex / Claude | ❌ Not built |
| Execution | Drafting | Codex / Claude | ❌ Not built |
| Execution | Orchestration | Make.com | ❌ Not built |
| Execution | Notifications | Slack (notifier.py) | ✅ Complete |

---

## Part VI: What ivan-task-manager Needs (Minimal)

To make the current system useful with entity/project awareness:

### 1. Entity Registry

A simple YAML file or folder structure:

```
entities/
  mark-smith-ai-branding.yaml
  kyle-stearns-ace-industrial.yaml
  yc-application.yaml
```

Each file contains the entity profile (see Layer 2 schema).

### 2. Task-Entity Mapping

Tasks know which entity they belong to:
- GitHub issues: Parse `[CLIENT:Mark]` from title
- ClickUp tasks: Use tags or custom field
- Or: Manual mapping file

### 3. Project/Workstream Deadlines

Projects have deadlines. Tasks without explicit deadlines inherit from their project.

### 4. Enhanced Scorer

Update scoring to consider:
- Project deadline (not just task deadline)
- Entity priority
- Workstream status (overdue workstream = all tasks urgent)

### 5. Context Display

`ivan next` shows entity context:
```
[Mark Smith / AI Branding Academy]
Project: System Setup (OVERDUE - was due Jan 25)
Task: Complete onboarding configuration
Why urgent: Showcase client, channel partner potential

🔗 https://clickup.com/t/...
📁 Context: entities/mark-smith-ai-branding.yaml
```

---

## Part VII: Phases

### Phase 0: Foundation ✅ (Complete as of 2026-01-28)

**Implementation Sprints Completed:**
- Sprint 1: Core (FastAPI, syncers, scoring, CLI)
- Sprint 2: Slack bot + notifications
- Sprint 3: Error handling, retry logic, CLI polish

**What's Working:**
- Task aggregation from ClickUp + GitHub (hourly sync with retry logic)
- Priority scoring (revenue, blocking, urgency, recency)
- CLI (`ivan next`, `done`, `skip`, `tasks`, `morning`, `sync`, `blocking`)
- Slack bot with natural language (Socket Mode, Azure OpenAI intent fallback)
- Smart notifications (instant alerts, morning briefings, hourly digests)
- Error categorization (auth, permission, rate_limit, timeout, connection, server)
- Exponential backoff retry (1s → 2s → 4s, max 30s)
- Graceful degradation (one source failure doesn't block others)
- Deployed on Railway: https://backend-production-7a52.up.railway.app

### Phase 1: Entity Awareness (NEXT)

- Entity registry (YAML files)
- Task-entity mapping (parse from titles/tags)
- Project deadlines in entity profiles
- Enhanced scoring with project urgency
- Context display in CLI

**Outcome:** Tasks show entity context and inherit deadlines.

### Phase 2: Context Capture

- Transcript processing workflow
- Email thread linking
- Meeting → tasks automation
- Entity context accumulation

**Outcome:** Context flows into entity profiles automatically.

### Phase 3: Agent Foundation

- Researcher agent (enrich entities)
- Drafter agent (create messages)
- Workflow execution framework
- Human approval flow

**Outcome:** Agents handle repeatable work.

### Phase 4: Scale + Learn

- Relationship nurturing at scale (20K contacts)
- Metrics and feedback loops
- Autonomy graduation (draft → auto)
- Vector search for context retrieval

**Outcome:** System handles volume and gets smarter.

---

## Part VIII: Non-Goals (For Now)

These are explicitly OUT OF SCOPE for Phase 1:

1. **Full agent infrastructure** — Agents come in Phase 3
2. **HubSpot integration** — Later, after basics work
3. **WhatsApp capture** — Manual for now
4. **Vector database** — Simple YAML files first
5. **Auto-send anything** — Human approval always
6. **Multi-user** — This is Ivan's personal system
7. **Mobile app** — CLI + Slack is enough

---

## Part IX: Success Criteria

### Phase 1 Success

- [ ] Every task shows its entity context
- [ ] Tasks inherit deadlines from projects
- [ ] `ivan next` shows WHY this task is priority
- [ ] No more "No deadline" for tasks in projects with deadlines
- [ ] Can add a new entity in < 5 minutes

### Overall Vision Success

- [ ] Ivan spends <30 min/day on task management
- [ ] Nothing falls through cracks
- [ ] Agents handle 80% of routine work
- [ ] System knows about all 20K contacts
- [ ] Context survives across sessions

---

## Part X: Open Questions

Parked for future consideration:

1. **Where do entity files live?** This repo? Separate repo? Google Drive?
2. **How to handle entities with no clear intention?** (Networking contacts)
3. **How to merge duplicate entities?** (Same person, different contexts)
4. **How to handle team members?** (Tamás, Attila interacting with same entities)
5. **What's the HubSpot migration path?** (When entity count gets large)
6. **How to handle confidential entities?** (Investors, legal matters)

---

## Appendix A: Entity Types

| Type | Examples | Key Fields |
|------|----------|------------|
| Client | Mark, Kyle | deal_value, contract_status |
| Prospect | New leads | stage, qualification |
| Partner | Channel partners, referrers | partnership_type, commission |
| Investor | VCs, angels | check_size, thesis_fit |
| Team | Tamás, Attila | role, responsibilities |
| Vendor | Service providers | contract, renewal_date |
| Network | General contacts | relationship_strength, last_touch |
| Company | Markster, YC | type: internal, application |

---

## Appendix B: Related Documents

- Agent System Bible: `/Work/agent-system/AGENT_SYSTEM_BIBLE.md`
- Markster Development Standards: `github.com/markster-exec/project-tracker/docs/standards`
- Current Design: `/docs/plans/2026-01-27-ivan-task-manager-design.md`

---

*This document is the product vision. Read it before building. Update it as understanding evolves. It should always answer: "What are we working towards?"*

**Last updated:** 2026-01-28
**Next review:** After Entity Awareness implementation
