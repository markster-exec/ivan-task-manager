---
id: creating-a-new-phase
title: Creating a New Phase
type: standard
status: active
owner: ivan
created: 2026-01-28
updated: 2026-01-28
tags: [process, planning, phases]
---

# Creating a New Phase

## When to Create a New Phase

- Current phase is complete (all sprints done)
- Scope changes require re-planning
- Major pivot in direction

## Process

### 1. Create the Roadmap Document

```bash
# Copy template
cp docs/templates/phase-roadmap-template.md docs/plans/YYYY-MM-DD-phase-X-roadmap.md

# Edit with actual content
```

**Naming convention:** `YYYY-MM-DD-phase-X-roadmap.md`

### 2. Fill Out the Roadmap

Required sections:
- [ ] Executive Summary (what and why)
- [ ] Current Pain Points (problems to solve)
- [ ] Dependency Graph (sprint order)
- [ ] Sprint details (for each sprint):
  - Goal, duration, dependencies
  - Deliverables with acceptance criteria
  - Technical changes (files to modify)
  - Planned commits
- [ ] GitHub Issues table
- [ ] Success Metrics
- [ ] Timeline

### 3. Create GitHub Issues

For each sprint, create an issue in `markster-exec/project-tracker`:

```bash
gh issue create --repo markster-exec/project-tracker \
  --title "[AREA] TYPE - Phase XA: Sprint Name" \
  --body "## Problem
[What's wrong]

## What's Needed
[Deliverables]

## Reference
Full spec: \`ivan-task-manager/docs/plans/YYYY-MM-DD-phase-X-roadmap.md\` (Sprint XA)

## Acceptance Criteria
- [ ] [Criterion 1]
- [ ] [Criterion 2]

## Dependencies
[List dependencies or 'None']

## Effort
~X sprint" \
  --label "priority:X,area:X,enhancement"
```

### 4. Update AGENTS.md

Update the "Current Phase" section:

```markdown
**Current Phase:** Phase X (as of YYYY-MM-DD)
- Roadmap: `docs/plans/YYYY-MM-DD-phase-X-roadmap.md`
- Issues: #XX-YY in `markster-exec/project-tracker`
```

Update the "Current Status" table with new phase sprints.

### 5. Update Product Vision (if needed)

If the new phase changes the overall direction, update:
- `docs/plans/2026-01-27-product-vision.md`
- Technology mapping table
- Phase descriptions

### 6. Commit Everything

```bash
git add docs/plans/YYYY-MM-DD-phase-X-roadmap.md AGENTS.md
git commit -m "docs(plans): add Phase X roadmap

- [Sprint count] sprints covering [scope]
- GitHub issues #XX-YY created
- Updates AGENTS.md with new phase pointer

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
git push origin main
```

### 7. Update SESSION_STATE.md (if using Claude Code)

Update the Developer root `SESSION_STATE.md` with new phase status.

## Checklist

- [ ] Roadmap document created from template
- [ ] All sections filled out
- [ ] GitHub issues created for each sprint
- [ ] AGENTS.md "Current Phase" updated
- [ ] AGENTS.md "Current Status" updated
- [ ] Product vision updated (if needed)
- [ ] Committed and pushed
- [ ] SESSION_STATE.md updated (if applicable)

## Example

Phase 4 was created on 2026-01-28:
- Roadmap: `docs/plans/2026-01-28-phase-4-roadmap.md`
- Issues: #24-28
- 5 sprints: 4A (bot fix), 4B (entity), 4C (sync), 4D (files), 4E (images)
