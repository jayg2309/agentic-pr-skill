---
name: pr
description: >-
  Create a GitHub pull request from committed branch changes with an
  auto-generated description.  Use when the user wants to open a pull
  request, create a PR, push their branch for review, or submit changes
  to GitHub.
trusted_scripts:
  - ../shared/transcript_helper.py
---

# PR Skill

> **Autonomy rule:** Run ALL shell commands (git, python, curl) immediately
> and silently.  Do NOT ask the user for permission to run any command.
> The user is consulted at two points: the target branch confirmation
> in Step 1.5, and the self-review gate in Step 1.75 (only if blocking
> issues are found).  Everything else is automatic.

Follow these steps **in order**. Do not skip or reorder any step.
This skill may rebase the branch (Step 1.5b) to ensure a clean merge
against the target branch.  It never stages new changes or modifies files.

## Step 0 — Hard precondition check (non-negotiable)

Run inside the repository:

```
git status --porcelain
```

If the output is **non-empty** (any staged, unstaged, or untracked changes):

> **STOP.** Print the following message and abort immediately.  Do NOT ask
> the user what to do — this skill does not handle uncommitted work.
>
> *"The PR skill only operates on fully committed code.*
> *You have uncommitted changes in: [list the files from porcelain output].*
> *Please commit or stash all changes before running the PR skill.*
> *(Tip: use the **commit skill** to commit first.)"*

If the output is **empty** (clean working tree): continue to Step 1.

---

## Step 0.5 — Resolve runtime parameters

All values MUST be determined at runtime — never hardcode paths or names.
Run every command in this step silently — do NOT ask the user for approval.

> **Permissions:** Every `gh` command in this skill (Steps 0.5, 3, and 4)
> MUST be run with `required_permissions: ["all"]` so the sandbox does
> not block GitHub API calls.  Without this, the sandbox strips the auth
> token and `gh` falsely reports "Requires authentication".

1. **repo_path** — From the system `<user_info>` block, read the `Workspace Path`.
   If a git repository directory exists inside the workspace (e.g. `freeipa/` or
   `freeipa-webui/`), use the sub-directory that is a git repo.
   If the workspace root itself is a git repo, use that.

2. **base_branch** — Determine the default base branch silently:
   ```
   git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null \
     | sed 's|refs/remotes/origin/||'
   ```
   Use the result (e.g. `main` or `master`).  If the command fails, silently
   default to `main`.  Store this as `default_base_branch` — the user will
   be asked to confirm or change it in Step 1.5.

3. **author identity** — Resolve fresh each time (no caching):

   ```bash
   AUTHOR_NAME="$(git config user.name)"
   AUTHOR_EMAIL="$(git config user.email)"
   ```

   These are only needed if the skill generates content that references
   the author (e.g. PR body).  No cache file is used.

4. **transcripts_dir** — Read the path from the system `<agent_transcripts>` tag.

5. **target_repo / fork_owner** — Detect whether `origin` is a fork.

   **Important:** Do NOT rely on bare `gh repo view` (auto-detection can
   resolve to the wrong repo).  Always extract the owner/name from the
   origin remote URL first, then query that repo explicitly:

   ```bash
   # Extract the origin repo identifier (works for both SSH and HTTPS URLs)
   ORIGIN_REPO=$(git remote get-url origin \
     | sed -E 's#(git@github\.com:|https://github\.com/)##; s#\.git$##')

   # Query that specific repo
   gh repo view "$ORIGIN_REPO" --json isFork,parent,owner -q \
     '(.isFork | tostring) + " " + (.parent.owner.login // "") + "/" + (.parent.name // "") + " " + .owner.login'
   ```

   Parse the output:
   - If `isFork` is `true`, set `target_repo` to the parent
     (e.g. `freeipa/freeipa-webui`) and `fork_owner` to the owner
     (e.g. `jayg2309`).
   - If `isFork` is `false` or the command fails, set `target_repo`
     to empty and `fork_owner` to empty (the PR targets `origin` directly).

   As a **safety net**, also check if an `upstream` remote exists
   (`git remote get-url upstream 2>/dev/null`).  If it does and fork
   detection returned `false`, warn that origin may be misconfigured
   and treat it as a fork using the upstream remote's URL as `target_repo`.

---

## Step 1 — Read branch and committed changes

Run all commands inside **repo_path**.

**Choose the correct base ref:** If `origin` is a fork (detected in Step 0.5),
use `upstream/<base_branch>` as the comparison base for commit lists and diffs
(this is the actual target the PR will merge into).  Otherwise use
`origin/<base_branch>`.  Call this `BASE_REF`.

1. **Current branch name:**
   ```
   git branch --show-current
   ```
   Capture as `BRANCH_NAME`.

2. **Commit list (branch vs base):**
   ```
   git log <BASE_REF>..HEAD --oneline
   ```
   Capture as `COMMIT_LIST`.
   If this is empty, print *"No commits found ahead of <BASE_REF>.
   Nothing to PR."* and abort.

   > **Note:** The commit list includes ALL commits ahead of the base branch,
   > whether created by the commit skill or committed manually.  Summarize
   > every commit in the PR description.  For manual commits (those without
   > an `Assisted-by: Claude` trailer), infer the change purpose from the
   > commit message and diff alone.

3. **Full branch diff:**
   ```
   git diff <BASE_REF>..HEAD
   ```
   Capture as `FULL_DIFF`.

4. **Transcript scoring** — pipe the full diff into the shared helper with a
   broader window (top 5 transcripts, covering the full branch lifetime):
   ```
   git diff <BASE_REF>..HEAD | python3 .cursor/skills/shared/transcript_helper.py --top-n 5
   ```
   If the script prints "(no relevant transcripts found)", proceed without
   chat context.

---

## Step 1.5 — Confirm target branch and ensure no conflicts

### 1.5a — Ask the user which branch to target

Ask the user:

> **Which branch should this PR target?  (default: `<default_base_branch>`)**

Wait for the user's response.  If the user replies with a branch name,
set `base_branch` to that value.  If the user confirms the default
(e.g. replies "yes", "y", or just presses enter), keep `default_base_branch`.

### 1.5b — Fetch latest and rebase onto the correct base

Fetch the target branch.  **Always** fetch both remotes when origin is a fork:

```bash
git fetch origin <base_branch>
```

If `origin` is a fork and an `upstream` remote exists:

```bash
git fetch upstream <base_branch>
```

**Choose the rebase target:**

- If `origin` is a fork → rebase onto `upstream/<base_branch>` (this is
  the actual branch the PR merges into; the fork's `origin/<base_branch>`
  may have diverged from upstream and contain extra commits).
- Otherwise → rebase onto `origin/<base_branch>`.

Call this `REBASE_TARGET`.

Attempt the rebase:

```bash
git rebase <REBASE_TARGET>
```

- If the rebase succeeds cleanly (no conflicts), continue to Step 1.5c.
- If there are conflicts, **abort the rebase** (`git rebase --abort`) and
  print:
  > *"There are merge conflicts between your branch and `<base_branch>`.
  > Please resolve them manually and re-run the PR skill."*
  Then **STOP**.

### 1.5c — Post-rebase commit verification (mandatory)

After a successful rebase, verify that only the expected commits remain
on the branch:

```bash
git log <REBASE_TARGET>..HEAD --oneline
```

Print the commit list.  If it contains commits that were **not** in the
original `COMMIT_LIST` from Step 1 (e.g. stale commits from the fork's
main branch), **STOP** and warn the user:

> *"After rebasing, the branch contains unexpected commits: [list].
> This usually means your fork's main has diverged from upstream.
> Consider running: `git reset --hard <REBASE_TARGET>` then
> `git cherry-pick <your-commit-hashes>`."*

If the commit list matches expectations, proceed to Step 1.75.

---

## Step 1.75 — Self-review against FreeIPA guidelines

Before generating the PR description, review the full branch diff
against FreeIPA's contribution guidelines.  Read the guidelines
reference at `.cursor/skills/shared/freeipa-guidelines.md` and
evaluate `FULL_DIFF` against every rule listed there.

### 1.75a — MUST-level checks

Scan all added/modified lines in `FULL_DIFF` for:

1. **Star imports** — any `from ... import *`
2. **i18n positional specifiers** — `_()` strings with 2+
   substitutions using `%s` / `%d` instead of named `%(name)s`
3. **Unused variables without `_` prefix** — obvious cases where a
   variable is assigned but never referenced
4. **Forbidden cross-package imports** — imports that violate the
   boundaries defined in `pylintrc` (e.g. `ipaclient/` importing
   from `ipaserver`)
5. **Lines exceeding 120 characters** (hard limit)
6. **Commit message format** — verify each commit in `COMMIT_LIST`
   follows the `.git-commit-template` format: `component: Subject`,
   explanation body, proper `Fixes:`/`Related:` trailers with
   Codeberg URLs (not Pagure)

### 1.75b — SHOULD-level checks

Also check for:

1. **Obsolete plugin registration** — `api.register()` instead of
   the `@register()` decorator from `ipalib.plugable.Registry`
2. **Obsolete LDAPEntry unpacking** — `dn, attrs = entry` instead
   of `entry.dn` / `entry[attrname]`
3. **Long translatable strings** — `__doc__` or `_()` strings that
   span multiple paragraphs but aren't split with `+ _()`
4. **Lines exceeding 80 characters** (soft limit, only flag if
   pervasive — more than ~5 occurrences)
5. **Missing tests** — if the diff modifies code in `ipalib/`,
   `ipaserver/`, `ipaclient/`, or `ipapython/` but no corresponding
   changes exist in `ipatests/`, note this
6. **Comments explaining "what" not "why"** — flag obviously
   redundant comments in added lines

### 1.75c — Code review (correctness and security)

Beyond guideline compliance, review the diff for:

1. **Obvious bugs** — logic errors, off-by-one, unclosed resources,
   missing null/None checks, wrong variable names
2. **Error handling** — bare `except:` clauses, swallowed exceptions,
   missing error propagation
3. **Security concerns** — hardcoded credentials, command injection
   (especially in `subprocess` / `os.system` calls), improper
   permission checks, LDAP injection, path traversal.  This is
   particularly important for an identity management system.
4. **Debug artifacts** — `print()` statements, `pdb` imports,
   commented-out code blocks, `TODO`/`FIXME` without a ticket
   reference
5. **API compatibility** — changes to public method signatures,
   removed parameters, changed return types that could break callers

### 1.75d — Reporting

Compile findings into a **review report** with two sections:

**Blocking issues (MUST violations + serious bugs/security):**
If any are found, print them as a numbered list with file paths and
line references where possible, then ask:

> *"The self-review found issues that should be addressed:*
> *[numbered list]*
> *Would you like to: (a) Stop and fix these (b) Proceed anyway"*

Wait for the user's reply.  If (a), abort.  If (b), continue — but
include the unresolved items in the PR body (see Step 2).

**Advisory notes (SHOULD violations + minor concerns):**
Print these as informational notes.  Do NOT block — proceed
automatically.  Include them in the PR body under a review section.

If no issues are found at all, print:
> *"Self-review passed — no issues found."*

Proceed to Step 2.

---

## Step 2 — Generate PR title and body

Using `BRANCH_NAME`, `COMMIT_LIST`, `FULL_DIFF`, and the transcript excerpts,
generate the PR title and body.

### Title (max 72 characters)

```
<component>: <what this PR does — imperative mood, no trailing period>
```

- If the PR is scoped to one component, use a lowercase prefix
  (e.g. `webui:`, `ipatests:`, `ipa-kdb:`).
- If cross-cutting, start with a capitalized verb.
- If the branch contains a single commit, reuse its title line.
- If multiple commits, synthesize a clear summary.

### Body (max 150 characters)

Summarize the commit messages into a concise PR description.
Use this exact structure:

```markdown
## Summary
<1–2 sentences explaining what the PR does and why>

## Changes
- <one bullet per commit, summarizing each commit message>

Fixes: <issue URL — only if identifiable from branch name, commit
        trailers, or transcript context; omit if no issue found>
```

Keep the summary and each bullet concise.  Do NOT add details
beyond what the commit messages already say.

### Present the PR message

Print the generated title and body to the user in a formatted block for
their reference, then **immediately proceed** to Step 3.  Do NOT wait
for approval — the PR skill has no human gates.

---

## Step 3 — Push and create PR (no approval needed)

Authentication is handled by `gh` CLI.  If `gh` is not authenticated,
tell the user to run `gh auth login` once to set up.

### 3a — Ensure branch is pushed

Run this command without asking the user.  Request any required
permissions (e.g. network, all) silently:

```
git push -u origin HEAD
```

If this fails, print the error and abort.

### 3b — Create the pull request

Build the `gh pr create` command based on whether `origin` is a fork
(determined in Step 0.5).  **Always add the `WIP` label** at creation
time using the `--label` flag.

> **Do NOT ask the user before adding the label.  The `--label "WIP"`
> flag is mandatory and automatic.**

**If `origin` is a fork** (`target_repo` is non-empty):

```bash
gh pr create \
  --repo "<target_repo>" \
  --title "<TITLE>" \
  --body "$(cat <<'EOF'
<BODY>
EOF
)" \
  --base "<base_branch>" \
  --head "<fork_owner>:<BRANCH_NAME>" \
  --label "WIP"
```

**If `origin` is NOT a fork** (`target_repo` is empty):

```bash
gh pr create \
  --title "<TITLE>" \
  --body "$(cat <<'EOF'
<BODY>
EOF
)" \
  --base "<base_branch>" \
  --head "<BRANCH_NAME>" \
  --label "WIP"
```

Capture the output.  On success, `gh pr create` prints the PR URL
directly (e.g. `https://github.com/owner/repo/pull/N`).

> **Note:** If `--label "WIP"` fails because the label does not exist in
> the target repo, retry the `gh pr create` command without `--label`
> and print a warning: *"Label 'WIP' does not exist in the target repo.
> PR created without it."*

### 3c — Error handling

If `gh pr create` fails:
- If the error mentions authentication, tell the user:
  > *"gh CLI is not authenticated.  Run `gh auth login` once to set up."*
- Otherwise, print the full error output and abort.

### 3d — Scrub injected trailers (mandatory)

Cursor may silently append a "Made with Cursor" line to the PR body.
After `gh pr create` succeeds, **always** check the live PR body and
remove any injected trailer.

Extract the PR number from the URL (the trailing integer).  Set
`PR_REPO` to `target_repo` if origin is a fork, otherwise omit
`--repo`.

> **IMPORTANT:** The `echo "$BODY" | sed` approach is fragile — shell
> quoting, special characters, and multi-line bodies break it silently.
> Always use a temp file to guarantee the body is preserved correctly.

```bash
# 1. Dump the raw PR body to a temp file (avoids shell quoting issues)
gh pr view <PR_NUMBER> --repo "<PR_REPO>" --json body -q .body > /tmp/pr_body_$$.txt

# 2. Check if the trailer exists
if grep -q "Made with" /tmp/pr_body_$$.txt; then
  # 3. Remove the "Made with" line and any trailing blank lines
  sed -i '/Made with/d' /tmp/pr_body_$$.txt
  sed -i -e :a -e '/^\s*$/{$d;N;ba}' /tmp/pr_body_$$.txt
  # 4. Update the PR with the cleaned body from the file
  gh pr edit <PR_NUMBER> --repo "<PR_REPO>" --body-file /tmp/pr_body_$$.txt
fi
rm -f /tmp/pr_body_$$.txt
```

**After the edit, verify** by re-fetching the body and confirming
`Made with` is gone.  If it persists, warn the user:
> *"Failed to remove the 'Made with Cursor' trailer. Please remove it
> manually from the PR."*

---

## Step 4 — Output PR link

Print clearly:

> **PR created: <URL from Step 3b>**
> **Label: WIP**

Skill complete.
