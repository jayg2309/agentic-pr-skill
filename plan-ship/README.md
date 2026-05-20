# Kickoff + Ship

Two Cursor agent skills: **`/kickoff`** turns a ticket into a plan;
**`/ship`** delivers it — code, tests, review, commit, and PR.

```
/kickoff PROJ-123   →   CONTEXT.md   →   /ship   →   Draft PR on GitHub
```

---

## Quick demo (60 seconds)

```text
1. /kickoff PROJ-123
     Agent reads Jira, scans repo structure, writes CONTEXT.md.
     You review the plan → "y"

2. /ship
     Agent implements → runs tests → reviews code → shows commit message.
     You approve → "y"
     Agent shows draft PR → you approve → "y"
     Draft PR is live on GitHub.
```

That's it. Two commands, three approval points, one `CONTEXT.md`.

---

## What's included

```
plan-ship/
├── README.md                        ← you are here
├── TROUBLESHOOTING.md               ← common issues + fixes
├── skills/
│   ├── kickoff/
│   │   └── SKILL.md                 ← /kickoff — ticket + repo → CONTEXT.md
│   ├── ship/
│   │   └── SKILL.md                 ← /ship — implement → test → review → commit → PR
│   └── shared/
│       ├── context-template.md      ← template for CONTEXT.md
│       └── transcript_helper.py     ← scores Cursor chat logs for commit/PR context
└── docs/
    └── ARCHITECTURE.md              ← diagrams, contracts, design decisions
```

---

## Installation

Copy the `skills/` folder into your target project:

```bash
cp -r plan-ship/skills/ <your-project>/.cursor/skills/
```

Cursor automatically discovers skills from `.cursor/skills/*/SKILL.md`.

---

## Prerequisites

### Required

| Tool | Purpose | Verify | Install |
|------|---------|--------|---------|
| **Cursor IDE** | Runs the agent skills | Open your project in Cursor | [cursor.com](https://cursor.com) |
| **Git** | Branch, diff, commit | `git --version` | Pre-installed on most systems |
| **Git identity** | Author on commits and PRs | `git config user.name` | `git config --global user.name "Your Name"` |
| **GitHub CLI** | Push, create PRs, resolve user | `gh --version` && `gh auth status` | See below |
| **Python 3** | Transcript scoring helper | `python3 --version` | Pre-installed on macOS/Linux |

**Install and authenticate `gh`:**

```bash
# macOS
brew install gh

# Fedora / RHEL
sudo dnf install gh

# Ubuntu / Debian
sudo apt install gh

# Then authenticate (one time)
gh auth login
```

### Recommended

Disable the Cursor commit trailer to keep commit messages clean:

**Cursor Settings UI:** search `commitMessageTrailer` → uncheck.

**Or** in `settings.json`:

```json
{
  "cursor.chat.commitMessageTrailer": false
}
```

### Optional — MCP servers (for `/kickoff` enrichment)

Kickoff uses whatever MCP servers you have configured.  Each is optional;
the skill degrades gracefully if a source is unavailable.

| MCP server | What kickoff reads | If missing |
|------------|-------------------|------------|
| **Jira** (Atlassian) | Ticket summary, AC, comments, links | Paste ticket text when prompted |
| **GitHub** | Issue title, body, comments, labels | `gh` CLI fallback (always works) |
| **Confluence** | Design docs, coding standards | Skipped; note in CONTEXT.md Links |
| **Slack** | Linked discussion threads (read-only) | Skipped |
| **Google Docs** | Spec documents | Skipped |

Configure MCPs in **Cursor Settings → MCP**.  Auth each server before
first use.

---

## Usage

### `/kickoff` — start from a ticket

```text
/kickoff RHOAIENG-1234
/kickoff https://github.com/org/repo/issues/42
/kickoff #42
/kickoff "Add retry logic to the data pipeline"
```

The agent will:
1. Read the ticket from Jira / GitHub / your text
2. Scan the codebase (structure, stack, test commands, PR template)
3. Estimate which files need changes
4. Write **`CONTEXT.md`** at the repo root
5. Show it for approval: **y / e / n**

### `/ship` — deliver the work

**Full pipeline** (all five phases):

```text
/ship
```

**Specific phases** (natural language):

```text
/ship implement
/ship run tests
/ship review my changes
/ship commit
/ship create pr
/ship test and commit
/ship review and then create a pr
```

The agent parses your intent, confirms the plan, then executes.

### Ship phases

| Phase | What happens | Human gate? |
|-------|-------------|-------------|
| **1. Implement** | Code changes from CONTEXT.md plan + project conventions | No (plan approved in kickoff) |
| **2. Test** | Discover and run repo test/lint commands; auto-fix failures | Only if 3 fixes fail |
| **3. Commit** | Generate message from CONTEXT.md + diff; local commit only | **y / e / n** |
| **4. Review** | 4-pass review (context, logic, security, quality); auto-fix | Only if 3 fix cycles fail |
| **5. PR** | Draft PR on GitHub following repo conventions | **y / e / n** |

Default full pipeline order: **1 → 2 → 4 → 3 → 5**
(review before commit, so fixes go into the same commit).

---

## How it works

### CONTEXT.md is the contract

Every phase reads and updates `CONTEXT.md`.  It carries:

- **What and why** — from the ticket
- **Project rules** — stack, patterns, conventions, test commands
- **Plan** — implementation steps you approved
- **Progress** — checkboxes updated as phases complete

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full contract
diagram and field-level mapping.

### Transcript scoring

The commit and PR phases optionally use `transcript_helper.py` to enrich
messages with context from your Cursor chat sessions.  It scores each
transcript against the diff:

- **60%** keyword overlap (paths, classes, functions from the diff)
- **40%** recency (full weight if modified in the last 24 hours)

Top excerpts are injected so commit/PR text reflects *why*, not just
*what*.

### Test discovery

Ship does not hardcode test commands.  Phase 2 scans `package.json`,
`Makefile`, `pyproject.toml`, CI workflows, and repo docs to find the
right commands.  Tests are scoped to changed files when possible.

On failure: diagnose, fix, re-run (up to 3 attempts).

### Review passes

Phase 4 runs four sequential checks:

1. **Context alignment** — does the diff satisfy each acceptance criterion?
2. **Logic and bugs** — race conditions, null checks, error paths
3. **Security** — injection, secrets, authz gaps
4. **Quality** — debug leftovers, dead code, typos

Output: `[STATUS]: NEEDS_WORK` with severity + fix diffs, or `[STATUS]: READY`.

### Commit mechanism

Phase 3 uses `git commit-tree` (low-level plumbing) instead of `git commit`
to bypass Cursor's auto-injected `Made-with:` trailer.  The commit message
is built from CONTEXT.md (why) + diff (what) + chat transcripts (intent).

### Fork-aware PR creation

Phase 5 detects whether `origin` is a fork, sets the correct `--head`
and `--repo` flags, and creates a `--draft` PR with a `WIP` label.
Post-creation, it scrubs any `Made with Cursor` trailer from the PR body.

---

## Human gates summary

| # | When | What you approve | Options |
|---|------|-----------------|---------|
| 1 | After `/kickoff` | CONTEXT.md (plan, scope, AC) | y = approve, e = edit, n = abort |
| 2 | Ship Phase 3 | Commit message | y = commit, e = edit, n = skip |
| 3 | Ship Phase 5 | PR title + body | y = create, e = edit, n = skip |

**`e` everywhere:** your next message IS the edited content.  No second
confirmation — the edit is the approval.

---

## Day-to-day workflow

```text
1. /kickoff PROJ-123              → CONTEXT.md, approve plan
2. /ship                           → full pipeline: code → test → review → commit → PR
3. (reviewers comment on GitHub)
4. /ship review and commit         → address feedback, re-commit
5. git push                        → draft PR updates
6. gh pr ready <number>            → leave draft state
```

Or step by step:

```text
1. /kickoff PROJ-123
2. /ship implement
3. /ship test
4. /ship review
5. /ship commit
6. /ship pr
```

---

## Competition day checklist

15 minutes before your demo:

- [ ] `gh auth status` → authenticated
- [ ] Demo repo open in Cursor, skills in `.cursor/skills/`
- [ ] MCP servers green in Cursor Settings (Jira, GitHub at minimum)
- [ ] Run `/kickoff <key>` once on a test ticket → `CONTEXT.md` on disk
- [ ] `git fetch origin` → base branch current
- [ ] Cursor commit trailer disabled
- [ ] Have a fallback ticket paragraph ready if Jira MCP fails live

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for solutions to common
issues:

- GitHub CLI not found or not authenticated
- MCP servers errored
- No CONTEXT.md found
- Test runner not discovered
- Rebase conflicts during PR
- Made-with-Cursor trailer appears
- Fork vs direct repo confusion
- And more

---

## Architecture

For diagrams, CONTEXT.md field mapping, MCP flexibility tables, and
phase selection logic, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
