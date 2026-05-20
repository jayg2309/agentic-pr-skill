---
name: ship
description: >-
  Flexible delivery pipeline: implement from CONTEXT.md, run repo-specific
  tests, review changes with context alignment, commit with precise messages,
  and create PRs following repo guidelines.  Supports natural language phase
  selection — say "/ship run tests" or "/ship commit" to start at any phase.
  Bare "/ship" runs the full pipeline.
trusted_scripts:
  - ../shared/transcript_helper.py
---

# Ship Skill

> **Autonomy rule:** Run ALL shell commands (git, test runners, linters)
> immediately and silently.  Human approval is required ONLY at these
> gates: **commit message** (Phase 3) and **PR body** (Phase 5).
> Everything else — implementation, testing, review, fixes — is automatic.

Follow the preamble first, then execute the resolved phases in order.

---

## Preamble — Intent parsing (mandatory, runs every invocation)

### P1 — Read CONTEXT.md

Read `CONTEXT.md` from the repository root.

If the file does **not** exist:

> Print: *"No CONTEXT.md found.  Run `/kickoff <ticket>` first to create
> one, or create CONTEXT.md manually."*
>
> **STOP.**

If CONTEXT.md exists, load its contents — all phases reference it.

### P2 — Parse user intent

Read the user's message **after** `/ship`.  Map it to one or more phases
using this keyword table:

| Keywords (case-insensitive) | Phase |
|-----------------------------|-------|
| "implement", "code", "build", "fix the bug", "do the ticket", "write code" | 1 — Implement |
| "test", "lint", "verify", "check", "run tests", "format" | 2 — Test |
| "commit", "save", "commit message", "stage" | 3 — Commit |
| "review", "check code", "LGTM", "pre-commit review", "find bugs" | 4 — Review |
| "pr", "pull request", "push", "create pr", "open pr", "send for review" | 5 — PR |

**Rules:**

- Multiple keywords → multiple phases, in pipeline order.
  Example: "test and commit" → phases 2, 3.
- **Bare `/ship`** (no extra text) → full pipeline: **1 → 2 → 4 → 3 → 5**.
- Unknown text → ask: *"I didn't understand which phases to run.
  Options: implement, test, commit, review, pr (or just `/ship` for all)."*

### P3 — Confirm plan

Print the planned phases clearly:

> **Planned phases:**
> 1. Implement
> 2. Test
> 4. Review (pre-commit)
> 3. Commit
> 5. Create PR
>
> **Proceed? (y / n)**

On **y** → execute phases in listed order.
On **n** → print *"Ship aborted."* and stop.

---

## Phase 1 — Implement

Read from CONTEXT.md:
- **Work item:** What, Why, Acceptance criteria
- **Project:** Stack, Layout, Patterns, conventions
- **Plan:** implementation steps
- **Scope:** expected files

### 1a — Branch

Run silently:

```bash
CURRENT_BRANCH=$(git branch --show-current)
```

If `CURRENT_BRANCH` is `main` or `master`:

1. Extract a ticket key from CONTEXT.md (e.g. `RHOAIENG-1234` or `#42`).
2. Generate a slug from the summary (lowercase, hyphens, max 40 chars).
3. Create and switch:

```bash
git checkout -b feature/<ticket-key>-<slug>
```

If already on a feature branch, stay on it.

### 1b — Code

Implement the changes described in CONTEXT.md **Plan** and **Scope**,
following the project's **Patterns** and **Layout** conventions.

**Rules:**
- Respect the project's naming conventions, directory structure, and
  architectural patterns recorded in CONTEXT.md **Project** section.
- Create only the files listed in **Scope** unless additional files are
  clearly required.
- Do NOT add comments that narrate what the code does.
- Do NOT introduce dependencies without noting them.

### 1c — Update progress

Update CONTEXT.md: check `[x] Implemented` in the Progress section.

---

## Phase 2 — Test (repo-dynamic, auto-fix on failure)

### 2a — Discover test/lint commands

Read these files (whichever exist) to find test and lint commands:

| File | Look for |
|------|----------|
| `README.md` | "Testing" or "Development" sections |
| `CONTRIBUTING.md` | Test instructions |
| `AGENTS.md` | Agent-specific test guidance |
| `package.json` | `scripts.test`, `scripts.lint`, `scripts.format`, `scripts.typecheck` |
| `Makefile` | `test`, `lint`, `check` targets |
| `pyproject.toml` / `setup.cfg` / `pytest.ini` | pytest configuration |
| `tox.ini` | `envlist` and commands |
| `Cargo.toml` | workspace test config |
| `.github/workflows/*.yml` | Test/lint commands from CI |

Also check CONTEXT.md **Test strategy** → **Automated** section for
pre-recorded commands from kickoff.

Build a **command list**: `[test_cmd, lint_cmd, format_cmd, ...]`

### 2b — Scope to changed files

```bash
CHANGED_FILES=$(git diff --name-only HEAD)
```

Narrow test commands when possible:

| Stack | Scoped command |
|-------|---------------|
| Jest | `npx jest --findRelatedTests <changed_test_files>` |
| pytest | `pytest <changed_test_files_or_dirs>` |
| Go | `go test ./<changed_packages>/...` |
| ESLint | `npx eslint <changed_js_ts_files>` |
| Ruff / flake8 | `ruff check <changed_py_files>` |

If scoping is not possible, run the repo's default command.

### 2c — Run and handle failures

For each command in the command list:

1. **Run the command** silently.
2. **On pass:** continue to the next command.
3. **On failure:**
   - Read the error output.
   - Diagnose the root cause.
   - **Fix the code** — apply the minimal change that resolves the failure.
   - **Re-run** the same command.
   - Repeat up to **3 fix attempts** per command.
   - After 3 failed attempts on the same command:

     > Print: *"Test/lint command `<cmd>` still failing after 3 fix attempts."*
     > Show the latest error output.
     > Ask: *"(r) retry with different approach / (s) skip this check / (a) abort ship"*

     | Reply | Action |
     |-------|--------|
     | **r** | Try one more fix with a different approach, then re-run |
     | **s** | Skip this command, continue to next |
     | **a** | Stop the entire ship pipeline |

### 2d — No test runner

If no test commands were discovered:

> Print: *"No test runner found in this repository.  Skipping automated
> tests.  Consider adding test commands to package.json, Makefile, or
> CONTEXT.md."*

Continue to next phase (do not block).

### 2e — Update progress

On all tests passing: update CONTEXT.md, check `[x] Tests green`.

---

## Phase 3 — Commit (local only, user approval required)

### 3a — Gather context

Run silently:

```bash
git status --porcelain
git diff
git diff --staged
git log --oneline -5
```

Also read:
- CONTEXT.md: ticket key, summary, AC (for the "why")
- Optional transcript enrichment:

```bash
git diff | python3 .cursor/skills/shared/transcript_helper.py --top-n 3
```

If transcript helper is not found or prints nothing, proceed without it.

### 3b — Stage files

If `git status --porcelain` shows unstaged changes but nothing staged:

1. Identify files to stage from the porcelain output.
2. **Never stage** files matching: `.env*`, `*credentials*`, `*secret*`,
   `*.pem`, `*.key`, `*token*`.  If detected, warn:
   > *"Skipping sensitive file: `<path>`.  Stage manually if intended."*
3. Stage remaining files:

```bash
git add <files>
```

If changes are already staged, use those.

If the working tree is **clean** (nothing to commit):

> Print: *"Working tree is clean — nothing to commit."*
> Skip to next phase.

### 3c — Generate commit message

Using the staged diff, CONTEXT.md, recent log, and transcript excerpts,
generate a commit message:

**Title line** (max 72 characters):

```
<component>: <short imperative description>
```

- If scoped to one component, prefix with lowercase name
  (e.g. `webui:`, `api:`, `tests:`).
- If cross-cutting, start with a capitalized verb.
- Include ticket key when available: `PROJ-123: fix null check in handler`
- Imperative mood.  No trailing period.

**Body** (blank line after title):

```
- <what changed and why — from CONTEXT.md + diff>
- <another change point>
```

Be specific: reference function names, file paths.  Do NOT invent
motivation — base on CONTEXT.md AC and the actual diff.

**Trailers** (blank line before this block):

```
Fixes: <issue URL — only if known from CONTEXT.md>
Signed-off-by: <author_name> <author_email>
```

### 3d — Human approval gate (mandatory — do NOT skip)

Show the complete commit message in a fenced code block.

Ask exactly:

> **Ready to commit with this message?  y / e / n**

| Reply | Action |
|-------|--------|
| **y** | Proceed to 3e immediately. |
| **e** | The user's **very next message** IS the edited commit message.  Commit immediately with that exact message — **no second confirmation**. |
| **n** | Print *"Commit skipped."*  Continue to next phase if any. |

### 3e — Execute the commit

Use `git commit-tree` to bypass IDE-injected trailers:

```bash
TREE=$(git write-tree)
PARENT=$(git rev-parse HEAD)
AUTHOR_NAME="$(git config user.name)"
AUTHOR_EMAIL="$(git config user.email)"
GITHUB_EMAIL="$(gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"' 2>/dev/null || echo "$AUTHOR_EMAIL")"

NEW_COMMIT=$(
  GIT_AUTHOR_NAME="$AUTHOR_NAME" \
  GIT_AUTHOR_EMAIL="$GITHUB_EMAIL" \
  GIT_COMMITTER_NAME="$AUTHOR_NAME" \
  GIT_COMMITTER_EMAIL="$GITHUB_EMAIL" \
  git commit-tree "$TREE" -p "$PARENT" <<'EOF'
<approved commit message here>
EOF
)

BRANCH=$(git branch --show-current)
git update-ref "refs/heads/$BRANCH" "$NEW_COMMIT"
git reset --hard "$NEW_COMMIT"
```

> **All `gh` commands use `required_permissions: ["all"]`.**

### 3f — Verify and report

```bash
git log -1 --format='%B' HEAD
```

Confirm no unwanted trailers (e.g. `Made-with:`).  If any appear, warn.

Print the short hash: `git rev-parse --short HEAD`

Print: *"Committed successfully.  No push — commit is local only."*

### 3g — Update progress

Update CONTEXT.md: check `[x] Committed`.

---

## Phase 4 — Review (context-aligned, multi-pass)

### 4a — Determine diff to review

- If changes are **uncommitted**: `git diff` (+ `git diff --staged`).
- If changes are **committed**: `git diff HEAD~1..HEAD` (or appropriate
  range from `origin/<base>..HEAD`).

### 4b — Review timing

If the user did NOT specify when to review (in their `/ship` message):

> Ask: *"When should I review?"*
> - **(a)** pre-commit — review now, before committing
> - **(b)** post-commit, pre-PR — review after commit, before PR
> - **(c)** skip review

Wait for answer.  In the **full pipeline** (bare `/ship`), default to
**(a) pre-commit** without asking.

### 4c — Execute review passes

Run four review passes against the diff and CONTEXT.md acceptance criteria.

**Pass 1 — Context alignment**

For each acceptance criterion in CONTEXT.md:
- Does the diff address it?
- Mark: SATISFIED / MISSING / PARTIAL

List any MISSING or PARTIAL criteria with explanation.

**Pass 2 — Logic and bugs**

Scan the diff for:
- Race conditions
- Null / undefined checks missing
- Off-by-one errors
- Incorrect error handling or swallowed exceptions
- Wrong assumptions about data shapes or API contracts

**Pass 3 — Security**

Scan for:
- Injection vulnerabilities (SQL, XSS, command injection)
- Secrets or credentials in code
- Authorization gaps
- Unsafe deserialization
- Hardcoded tokens or API keys

**Pass 4 — Quality**

Scan for:
- Debug leftovers: `console.log`, `debugger`, `print()`, `TODO`/`FIXME`
  without ticket reference
- Commented-out dead code
- Obvious typos in user-facing strings or identifiers
- Missing error messages or unhelpful error text

### 4d — Output format

Start with exactly one status line:

**If any finding exists:**

```
[STATUS]: NEEDS_WORK
```

Then for each finding:

```
[SEVERITY] path/to/file.ts:42 — Short title
  Explanation (1-2 sentences).
  Fix:
  ```diff
  - broken line
  + fixed line
  ```
```

Severity levels: `[CRITICAL]`, `[HIGH]`, `[MEDIUM]`, `[LOW]`

**If no findings:**

```
[STATUS]: READY
```

No generic praise.  No summary of "what the code does."

### 4e — Auto-fix on NEEDS_WORK

If status is `NEEDS_WORK`:

1. For each finding rated `CRITICAL` or `HIGH`: apply the fix automatically.
2. For `MEDIUM` / `LOW`: apply if the fix is unambiguous; skip if judgment
   is needed.
3. Re-run the review (passes 1–4) on the updated diff.
4. Repeat up to **3 fix-review cycles**.
5. If still `NEEDS_WORK` after 3 cycles:

   > Print remaining findings.
   > Ask: *"Some issues remain.  (f) force continue / (a) abort ship"*

### 4f — Update progress

On `READY`: update CONTEXT.md, check `[x] Reviewed`.

---

## Phase 5 — Create PR

### 5a — Precondition check

```bash
git status --porcelain
```

If output is **non-empty** (uncommitted changes exist):

> Print: *"You have uncommitted changes.  Run `/ship commit` first or
> stage and commit manually before creating a PR."*
> **STOP this phase.**

### 5b — Resolve runtime parameters

> **All `gh` commands use `required_permissions: ["all"]`.**

```bash
# Base branch
BASE_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null \
  | sed 's|refs/remotes/origin/||')
BASE_BRANCH=${BASE_BRANCH:-main}

# Current branch
BRANCH_NAME=$(git branch --show-current)

# Fork detection
ORIGIN_REPO=$(git remote get-url origin \
  | sed -E 's#(git@github\.com:|https://github\.com/)##; s#\.git$##')

gh repo view "$ORIGIN_REPO" --json isFork,parent,owner -q \
  '(.isFork | tostring) + " " + (.parent.owner.login // "") + "/" + (.parent.name // "") + " " + .owner.login'
```

Parse: if fork → `TARGET_REPO` = parent, `FORK_OWNER` = owner.
If not fork → `TARGET_REPO` = empty, `FORK_OWNER` = empty.

Set `BASE_REF`:
- Fork: `upstream/<BASE_BRANCH>` (fetch upstream first)
- Direct: `origin/<BASE_BRANCH>`

### 5c — Gather commit list and diff

```bash
git fetch origin "$BASE_BRANCH"
git log "$BASE_REF"..HEAD --oneline
git diff "$BASE_REF"..HEAD
```

If no commits ahead: print *"No commits ahead of `<BASE_REF>`. Nothing to
PR."* and stop.

### 5d — Discover PR conventions

Check for PR template (in order):
1. `.github/PULL_REQUEST_TEMPLATE.md`
2. `.github/pull_request_template.md`
3. `.github/PULL_REQUEST_TEMPLATE/` directory
4. `CONTRIBUTING.md` PR sections

If a template exists, use its structure for the PR body.
If not, use the default structure below.

### 5e — Generate PR title and body

**Title** (max 72 characters):

- Single commit → reuse its title line.
- Multiple commits → synthesize from CONTEXT.md summary.
- Component prefix if scoped.

**Body** (default structure, or repo template):

```markdown
## Summary
<1-2 sentences from CONTEXT.md Why + What>

## Changes
- <one bullet per commit>

## Test plan
- [x] <automated tests that passed in Phase 2>
- [ ] <manual verification steps from CONTEXT.md>

Fixes: <issue URL from CONTEXT.md if known>
```

Optional enrichment:

```bash
git diff "$BASE_REF"..HEAD | python3 .cursor/skills/shared/transcript_helper.py --top-n 5
```

### 5f — Show draft and get approval (mandatory)

Print the PR in chat:

```markdown
## Draft PR (not created yet)

**Branch:** `<BRANCH_NAME>` → `<BASE_BRANCH>`
**Type:** GitHub draft PR + label `WIP`

**Title:** `<TITLE>`

**Description:**
<BODY>

**Commits:**
<COMMIT_LIST>
```

Ask exactly:

> **Open this PR?  (y) create / (e) edit / (n) abort**

| Reply | Action |
|-------|--------|
| **y** | Proceed to 5g with generated title/body. |
| **e** | Next user message replaces title (first line) and body (rest).  Proceed to 5g immediately — **no re-ask**. |
| **n** | Print *"PR skipped."* and stop. |

### 5g — Push and create PR

```bash
git push -u origin HEAD
```

On push failure, print error and stop.

**If fork** (`TARGET_REPO` is set):

```bash
gh pr create \
  --repo "<TARGET_REPO>" \
  --draft \
  --title "<TITLE>" \
  --body "$(cat <<'EOF'
<BODY>
EOF
)" \
  --base "<BASE_BRANCH>" \
  --head "<FORK_OWNER>:<BRANCH_NAME>" \
  --label "WIP"
```

**If not a fork:**

```bash
gh pr create \
  --draft \
  --title "<TITLE>" \
  --body "$(cat <<'EOF'
<BODY>
EOF
)" \
  --base "<BASE_BRANCH>" \
  --head "<BRANCH_NAME>" \
  --label "WIP"
```

If `--label "WIP"` fails (label doesn't exist), retry without `--label`
and warn: *"Label 'WIP' does not exist in the target repo.  PR created
without it."*

### 5h — Scrub injected trailers

After `gh pr create` succeeds, check and clean the live PR body:

```bash
PR_NUMBER=<from URL>

gh pr view "$PR_NUMBER" --json body -q .body > /tmp/pr_body_$$.txt

if grep -q "Made with" /tmp/pr_body_$$.txt; then
  sed -i '/Made with/d' /tmp/pr_body_$$.txt
  sed -i -e :a -e '/^\s*$/{$d;N;ba}' /tmp/pr_body_$$.txt
  gh pr edit "$PR_NUMBER" --body-file /tmp/pr_body_$$.txt
fi
rm -f /tmp/pr_body_$$.txt
```

Add `--repo "<TARGET_REPO>"` to both commands if origin is a fork.

Verify: re-fetch body, confirm `Made with` is gone.  If it persists, warn.

### 5i — Report

Print:

> **Draft PR created:** \<URL\>
> **State:** Draft (not ready for review)
> **Label:** WIP
>
> **For reviewers:** comment on GitHub — inline review works on draft PRs.
> **When ready:** `gh pr ready <PR_NUMBER>` or use GitHub UI.
> **After feedback:** fix code → `/ship commit` → `git push` → draft
> updates automatically.

### 5j — Update progress

Update CONTEXT.md: check `[x] PR opened`, add the PR URL.

---

## Phase ordering reference

### Full pipeline (bare `/ship`)

```
Phase 1 (Implement)
  → Phase 2 (Test — fix failures)
  → Phase 4 (Review — pre-commit, fix NEEDS_WORK)
  → Phase 3 (Commit — y/e/n gate)
  → Phase 5 (Create PR — y/e/n gate)
```

### Partial runs (user specifies phases)

Execute only the requested phases, in pipeline order (1→2→4→3→5),
regardless of the order the user typed them.

If review timing is ambiguous in a partial run (e.g. user says "review
and commit"), ask (a) pre-commit / (b) post-commit before proceeding.

---

## Error handling summary

| Situation | Action |
|-----------|--------|
| No CONTEXT.md | STOP with message to run `/kickoff` |
| Unrecognized `/ship` intent | Ask user to clarify phases |
| On `main`/`master` at implement | Create feature branch from CONTEXT.md ticket key |
| Test failure after 3 fix attempts | Ask: retry / skip / abort |
| Review NEEDS_WORK after 3 cycles | Ask: force continue / abort |
| Nothing to commit (clean tree) | Skip Phase 3, continue |
| Uncommitted changes at PR phase | STOP, ask to commit first |
| No commits ahead of base | STOP, nothing to PR |
| `gh` not authenticated | Print: *"Run `gh auth login` to authenticate."* |
| Push fails | Print error, stop PR phase |
| WIP label missing in repo | Create PR without label, warn |
| Transcript helper not found | Proceed without chat context |
| Sensitive files detected in stage | Skip them, warn user |
| Made-with trailer persists | Warn user to remove manually |
