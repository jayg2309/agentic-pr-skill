---
name: kickoff
description: >-
  Read a Jira ticket, GitHub issue, or any work item via configured MCPs,
  analyze the project structure and design philosophy from the codebase,
  then write CONTEXT.md with task scope, acceptance criteria, file estimates,
  test strategy, and implementation plan.  Use when starting work on a ticket,
  issue, or feature request.
---

# Kickoff Skill

> **Autonomy rule:** Run ALL shell commands and MCP read calls immediately
> and silently.  Do NOT ask the user for permission to gather information.
> The ONLY point where the user is consulted is the plan approval gate in
> Step 5.  Everything before that is automatic.

Follow these steps **in order**.  Do not skip or reorder any step.

---

## Step 0 — Parse user input

The user invokes this skill with one anchor — a ticket reference or
plain-text description.  Detect the type:

| Pattern | Type | Example |
|---------|------|---------|
| `[A-Z][A-Z0-9]+-\d+` | Jira key | `RHOAIENG-1234` |
| URL containing `atlassian.net/browse/` or `issues.redhat.com/browse/` | Jira URL | `https://redhat.atlassian.net/browse/RHOAIENG-1234` |
| URL containing `github.com/.*/issues/\d+` | GitHub issue | `https://github.com/org/repo/issues/42` |
| `#\d+` (when in a GitHub repo) | GitHub issue (short) | `#42` |
| Anything else | Plain text | "Add dark mode toggle to settings page" |

Store the detected **type** and **value** for Step 1.

---

## Step 1 — Fetch work-item context (MCP-flexible)

> **Permissions:** Every `gh` command MUST use `required_permissions: ["all"]`
> so the sandbox does not block GitHub API calls.

### 1a — MCP discovery

Before calling any MCP tool, **read the tool's JSON schema** under the
server's `tools/` folder.  If the server's `STATUS.md` indicates it needs
authentication, call `mcp_auth` for that server first.

### 1b — Fetch from detected source

**Jira path** (when Jira MCP is available and input is a Jira key/URL):

1. Call `jira_get_issue` with the key — capture summary, description,
   acceptance criteria, labels, priority, status, and linked issues.
2. If linked issues exist, call `jira_get_issue` for each (max 3) to
   understand related context.
3. Scan description and comments for links to Confluence pages, Slack
   threads, GitHub PRs, or Google Docs.

**GitHub path** (when input is a GitHub issue URL/number):

1. Run `gh issue view <number> --json title,body,comments,labels` with
   `required_permissions: ["all"]`.
2. Or use GitHub MCP `issue_read` if available.
3. Scan body and comments for linked Jira keys, Slack threads, or docs.

**Plain-text path** (no external source):

1. Use the user's text as the work-item description.
2. Skip to Step 2 — no MCP calls needed.

### 1c — Enrich from linked sources (optional, best-effort)

For each linked resource discovered in 1b:

| Source | Tool | Action |
|--------|------|--------|
| Confluence page | Atlassian MCP (`confluence_get_page`) or skip | Fetch page content for design context |
| Slack thread | Slack MCP (`get_thread`) — **read-only** | Fetch discussion for requirements clarity |
| Google Docs | Google Docs MCP if configured | Fetch spec content |
| GitHub PR | `gh pr view` or GitHub MCP | Fetch related implementation context |

**If any MCP fails:** Log which source was unreachable and continue.
Do NOT stop the skill for optional enrichment failures.

### 1d — Fallback

If the primary source (Jira or GitHub) is unreachable after auth attempts:

> Print: *"Could not reach <source>.  Please paste the ticket
> description and acceptance criteria, and I'll continue from there."*

Wait for the user's paste, then use that text as work-item context.

---

## Step 2 — Analyze project structure and philosophy

Run all commands silently inside the workspace repository.

### 2a — Directory layout

```bash
# Project tree (2 levels, skip noise)
find . -maxdepth 2 -type f -name "*.md" | head -30
ls -la
```

If `tree` is available:
```bash
tree -L 2 -I 'node_modules|.git|__pycache__|dist|build|vendor|target' --dirsfirst
```

### 2b — Project documentation

Read whichever of these exist (first 100 lines each):

- `README.md`
- `CONTRIBUTING.md`
- `AGENTS.md`
- `.cursor/rules/*.md` or `.cursor/rules/*.mdc`
- `docs/ARCHITECTURE.md` or `docs/architecture.md`

### 2c — Build and test stack

Detect the project's toolchain by checking for these files:

| File | Stack | Extract |
|------|-------|---------|
| `package.json` | Node/JS/TS | `scripts` block (test, lint, build, format commands) |
| `Makefile` | Make-based | test/lint/build targets |
| `pytest.ini` / `setup.cfg` / `pyproject.toml` | Python | test runner config, paths |
| `go.mod` | Go | module path |
| `Cargo.toml` | Rust | workspace members, test config |
| `.github/workflows/*.yml` | CI | test/lint commands used in CI |
| `tox.ini` | Python (tox) | envlist, test commands |

Record discovered **test commands**, **lint commands**, and **build commands**.

### 2d — PR conventions

Check for:

- `.github/PULL_REQUEST_TEMPLATE.md` or `.github/pull_request_template.md`
- `CONTRIBUTING.md` sections about PRs
- Any PR template in `.github/PULL_REQUEST_TEMPLATE/`

Record the path or "none found".

### 2e — Design philosophy

From the documentation gathered in 2b, extract:

- Architectural patterns (MVC, component-based, microservices, monorepo, etc.)
- Naming conventions (file naming, function naming, CSS methodology)
- State management approach
- Error handling patterns
- Import organization rules

Summarize in 3–5 bullet points.  If documentation is sparse, infer
from directory structure and code patterns (skim 2–3 representative
source files).

---

## Step 3 — Estimate file scope

Using the work-item context from Step 1 and the project structure from
Step 2:

1. **Search the codebase** for components, functions, files, or modules
   mentioned in the ticket description or acceptance criteria.
2. **List likely files** to create or modify in a table:

   | Area | Files (expected) | Notes |
   |------|------------------|-------|
   | ... | `path/to/file.ts` | Modify: add X |
   | ... | `path/to/new.ts` | Create: new component |

3. **Count estimate:** "~N files"

Be conservative — list files you are reasonably confident need changes,
not every transitive dependency.

---

## Step 4 — Write CONTEXT.md

Read the template at `.cursor/skills/shared/context-template.md` (or use
the structure below if the template is not found).

Fill every section using data from Steps 1–3:

```markdown
# Context: <TICKET_KEY or short title>

## Work item
- **Source:** <Jira KEY / GitHub #N / URL>
- **Summary:** <one-line summary from ticket>
- **Why:** <problem statement / user impact from ticket>
- **Acceptance criteria:**
  - [ ] <AC 1 from ticket>
  - [ ] <AC 2 from ticket>

## Scope
| Area | Files (expected) | Notes |
|------|------------------|-------|
| <from Step 3> | | |

**Estimated touch:** ~N files

## Plan
1. <implementation step 1>
2. <implementation step 2>
...
- [ ] Plan approved

## Project
- **Repo:** <repo name>
- **Stack:** <language, framework from Step 2c>
- **Layout:** <key directories from Step 2a>
- **Patterns:** <design philosophy from Step 2e>
- **Test commands:** <from Step 2c>
- **Lint/format:** <from Step 2c>
- **PR template:** <from Step 2d>

## Test strategy
### Automated
- Command: `<discovered test command scoped to changed files>`
- Scope: <which test files or patterns>
### Manual (if applicable)
- Steps: <based on ticket AC or known environment>

## Progress
- [ ] Kickoff complete
- [ ] Plan approved
- [ ] Implemented
- [ ] Tests green
- [ ] Reviewed
- [ ] Committed
- [ ] PR opened

## Links
- <Source>: <URL>
- <Any linked Confluence, Slack, doc URLs discovered in Step 1c>
```

Write this file to the **repository root** as `CONTEXT.md`.

---

## Step 5 — Human approval gate (mandatory — do NOT skip)

Print the complete `CONTEXT.md` content to chat inside a fenced block
so the user can review it.

Then ask exactly:

> **Plan looks good?  (y) approve / (e) edit / (n) abort**

Wait for the user's response.

| Reply | Action |
|-------|--------|
| **y** | Update `CONTEXT.md`: check the "Kickoff complete" and "Plan approved" boxes.  Print: *"Kickoff complete.  Run `/ship` to start delivering, or `/ship implement` to begin coding."* |
| **e** | The user's **very next message** contains their edits.  Apply the edits to `CONTEXT.md`, check both boxes, and proceed — **no second approval**.  The edit IS the approval. |
| **n** | Delete `CONTEXT.md`.  Print: *"Kickoff aborted — CONTEXT.md removed."* |

---

## Error handling summary

| Situation | Action |
|-----------|--------|
| Primary MCP (Jira/GitHub) unreachable | Fallback: ask user to paste text (Step 1d) |
| Optional MCP (Confluence/Slack/Docs) fails | Skip silently, note in Links section |
| No README or project docs found | Infer from directory structure and code; note sparse docs in Project section |
| No test commands discovered | Write "none discovered" in Test strategy; note in CONTEXT.md |
| `gh` not installed | Print: *"GitHub CLI not found. Install with `brew install gh` (macOS) or `sudo dnf install gh` (Fedora), then `gh auth login`."* |
| User input is ambiguous (could be Jira or plain text) | Ask: *"Is '<input>' a Jira key or a plain description?"* |
| Repo has no `.git` | Print: *"No git repository found. Initialize with `git init` first."* |
