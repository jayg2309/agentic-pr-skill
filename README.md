# Cursor Commit & PR Skills

AI-powered agent skills for Cursor IDE that automate Git commit messages and GitHub pull request creation.

## What's Included

```
.cursor/skills/
├── commit/
│   └── SKILL.md              # Commit skill — generates commit messages from diffs + chat context
├── pr/
│   └── SKILL.md              # PR skill — creates GitHub PRs via gh CLI
└── shared/
    ├── freeipa-guidelines.md  # FreeIPA contribution guidelines (agent review reference)
    └── transcript_helper.py   # Scores Cursor chat transcripts for relevance to a diff
```

## One-Time Setup (every team member)

### 1. Install and authenticate the GitHub CLI

```bash
# Install gh (if not already installed)
# Fedora/RHEL:
sudo dnf install gh
# macOS:
brew install gh
# Ubuntu/Debian:
sudo apt install gh

# Authenticate (follow the browser prompts)
gh auth login
```

This is the only authentication step needed. No tokens, no `.env` files.

### 2. Set your Git identity

Make sure your Git name and email are configured:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

The skills read these values fresh on each run.

### 3. Disable the "Made-with: Cursor" commit trailer

Cursor appends a `Made-with: Cursor` line to every commit by default. To disable it, add this to your Cursor settings:

**Option A — Via Cursor settings UI:**
1. Open Cursor Settings (`Ctrl+,` / `Cmd+,`)
2. Search for `commitMessageTrailer`
3. Uncheck the box

**Option B — Edit settings.json directly:**
1. Open the command palette (`Ctrl+Shift+P` / `Cmd+Shift+P`)
2. Type "Preferences: Open User Settings (JSON)"
3. Add this line:

```json
"cursor.chat.commitMessageTrailer": false
```

## Usage

### Commit Skill

Stage your changes, then invoke the skill:

> `/commit`

The agent will:
1. Detect the staged diff and gather context from recent chat transcripts
2. Check the diff against FreeIPA contribution guidelines (star imports, i18n formatting, naming, forbidden imports, line length)
3. Generate a structured commit message (component prefix, bullet points, trailers)
4. Show you the message and ask for approval: **y** / **e** / **n**
5. Commit on your approval

### PR Skill

Once all changes are committed, invoke the skill:

> `/pr`

The agent will:
1. Gather all commits ahead of the base branch (including any manual commits)
2. Confirm the target branch with you, then rebase to ensure a clean merge
3. Run a self-review against FreeIPA contribution guidelines and check for bugs, security issues, and missing tests
4. Generate a PR title and structured body (Summary, Changes, Review Notes)
5. Push the branch and create the PR via `gh pr create`
6. Print the PR URL

## How It Works

### Guideline Validation & Self-Review

Both skills validate code changes against FreeIPA's upstream contribution standards, compiled in `shared/freeipa-guidelines.md` from the official documentation:

**At commit time (Step 2.5):** A quick scan of the staged diff checks for MUST-level violations — star imports, i18n positional specifiers, unnamed dummy variables, forbidden cross-package imports, and line length. MUST violations prompt you to fix before committing; SHOULD violations are shown as informational notes.

**At PR time (Step 1.75):** A comprehensive self-review covers:
- **Guideline compliance** — all MUST and SHOULD rules from the FreeIPA contribution guidelines
- **Correctness** — logic errors, missing error handling, unclosed resources
- **Security** — hardcoded credentials, command/LDAP injection, improper permission checks
- **Completeness** — missing tests for code changes, debug artifacts left in
- **Commit message format** — verifies each commit follows the `.git-commit-template`

Blocking issues (MUST violations + serious bugs/security) require your approval to proceed. Advisory notes are included in the PR body under a **Review Notes** section.

### Transcript Scoring

Both skills use `transcript_helper.py` to find relevant Cursor agent chat transcripts. It extracts identifiers from the diff (file paths, function names, class names) and scores each transcript by:

- **Keyword overlap** (60% weight) — how many diff tokens appear in the transcript
- **Recency** (40% weight) — bonus for transcripts modified within the last 24 hours

The top-scoring transcripts provide the "why" context for commit messages and PR descriptions.

## Troubleshooting

For common errors and how to resolve them, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
