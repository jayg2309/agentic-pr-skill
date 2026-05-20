# Troubleshooting

Common issues with `/kickoff` and `/ship`, and how to resolve them.

---

### GitHub CLI not found

**Error:** `gh: command not found`

The `gh` CLI is required for PR creation and GitHub email resolution.

```bash
# macOS
brew install gh

# Fedora / RHEL
sudo dnf install gh

# Ubuntu / Debian
sudo apt install gh
```

Then authenticate once:

```bash
gh auth login
```

---

### GitHub authentication failure

**Error:** `gh: Requires authentication` or `HTTP 401`

This usually means `gh` is not logged in, or the Cursor sandbox stripped
the auth token.

```bash
# Check current auth status
gh auth status

# Re-authenticate if needed
gh auth login
```

If `gh` works in your terminal but fails inside the skill, verify the
skill uses `required_permissions: ["all"]` for every `gh` command.  Both
`kickoff/SKILL.md` and `ship/SKILL.md` already specify this.

---

### MCP server errored (Jira, GitHub, Confluence)

**Error:** *"Could not reach \<source\>."* during `/kickoff`

The MCP server failed to connect.  Check its status in
**Cursor Settings → MCP**.

Common causes:
- **Jira:** `uvx mcp-atlassian` failing to start, expired API token,
  network/SSL issues.
- **GitHub:** Copilot MCP auth failure or expired PAT.
- **Confluence:** Server not configured or needs authentication.

**Fix:**
1. Open Cursor Settings → MCP → find the errored server.
2. Check error details and re-authenticate if needed.
3. Restart the MCP server from Settings.

**Workaround:** When kickoff cannot reach the primary source, it asks you
to paste the ticket text.  The skill continues with your pasted content.

---

### No CONTEXT.md found

**Error:** *"No CONTEXT.md found. Run `/kickoff` first or create one manually."*

Ship requires `CONTEXT.md` at the repository root.  Create it either way:

```bash
# Option 1: Run kickoff
/kickoff PROJ-123

# Option 2: Copy the template and fill manually
cp .cursor/skills/shared/context-template.md CONTEXT.md
# Edit CONTEXT.md with your ticket details
```

---

### Jira MCP fails — fallback to paste

**Message:** *"Could not reach Jira. Please paste the ticket description
and acceptance criteria."*

This is expected behavior, not an error.  Paste the relevant text from
your Jira ticket (summary, description, acceptance criteria) and kickoff
will continue normally.

To fix the MCP for future runs, check Cursor Settings → MCP → Jira server
for auth or connection errors.

---

### No test runner discovered

**Message:** *"No test runner found in this repository."*

Ship Phase 2 scans `package.json`, `Makefile`, `pyproject.toml`, CI
workflows, and repo docs for test commands.  If nothing is found:

1. The skill skips tests and continues (does not block).
2. A warning is recorded in CONTEXT.md.

**Fix for future runs:**

- Add test commands to your project (`package.json` scripts, `Makefile`
  targets, `pyproject.toml` config).
- Or add them manually to CONTEXT.md **Test strategy → Automated** section
  before running `/ship test`.

---

### Test failures after 3 fix attempts

**Message:** *"Test/lint command `<cmd>` still failing after 3 fix attempts."*

The agent tried to diagnose and fix the failing test/lint three times
without success.

Options when prompted:
- **(r) retry** — the agent tries a different fix approach.
- **(s) skip** — skip this check and continue to the next phase.
- **(a) abort** — stop the entire ship pipeline.

If you skip, the test failure is recorded but does not block commit/PR.
Consider fixing manually and re-running `/ship test` before committing.

---

### Review stuck on NEEDS_WORK

**Message:** *"Some issues remain."* after 3 fix-review cycles.

The review found issues that the agent could not fully auto-fix.

Options when prompted:
- **(f) force continue** — proceed despite remaining issues (they will
  appear in your diff/PR for manual handling).
- **(a) abort** — stop the ship pipeline.

Common reasons for persistent findings:
- Ambiguous acceptance criteria (review cannot determine if AC is met).
- Architectural issues that require human judgment.
- False positives in security or logic checks.

---

### Wrong base branch detected

**Error:** The skill targets `master` when it should target `main`
(or vice versa).

The skills detect the default branch via `origin/HEAD`.  If this is wrong
or unset:

```bash
# Auto-detect and set origin/HEAD
git remote set-head origin --auto

# Verify
git symbolic-ref refs/remotes/origin/HEAD
```

---

### Rebase conflicts during PR

**Error:** *"There are merge conflicts between your branch and `<base>`."*

Ship Phase 5 may attempt a rebase before PR creation.  On conflict, the
rebase is aborted automatically.

Resolve manually:

```bash
# Fetch latest and rebase
git fetch origin main
git rebase origin/main

# Resolve conflicts in each file, then:
git add <resolved-file>
git rebase --continue

# Once clean, re-run the PR phase
/ship pr
```

---

### Made-with-Cursor trailer appears

Ship Phase 3 uses `git commit-tree` specifically to avoid this trailer.
If it still appears:

1. Disable the setting in Cursor:

   ```json
   "cursor.chat.commitMessageTrailer": false
   ```

2. To fix an existing commit:

   ```bash
   git commit --amend --no-edit
   # Then manually remove the trailer line
   ```

Ship Phase 5 also scrubs `Made with` lines from the PR body after
creation using `gh pr edit`.

---

### Push fails when creating PR

**Error:** `git push -u origin HEAD` fails.

Common causes:

```bash
# No remote configured
git remote -v
git remote add origin git@github.com:you/repo.git

# Branch already exists on remote with different history
git push -u origin HEAD --force-with-lease

# SSH key not configured
ssh -T git@github.com
```

---

### PR template not detected

**Message:** Ship Phase 5 uses the default `## Summary / ## Changes / ## Test plan`
structure instead of your repo's template.

Ship checks these paths in order:
1. `.github/PULL_REQUEST_TEMPLATE.md`
2. `.github/pull_request_template.md`
3. `.github/PULL_REQUEST_TEMPLATE/` directory

If your template is elsewhere, either move it to a standard location or
add the PR body structure to CONTEXT.md manually.

---

### Fork vs direct repo confusion

Ship Phase 5 detects forks via `gh repo view`.  If it gets the wrong
result:

```bash
# Check what origin points to
git remote -v

# Check fork status manually
gh repo view <owner/repo> --json isFork,parent
```

If origin is a fork but detection fails:
- Ensure an `upstream` remote exists:

  ```bash
  git remote add upstream https://github.com/org/original-repo.git
  ```

- Ship uses `upstream` as a safety net when fork detection returns false
  but an upstream remote exists.

---

### Transcript helper finds nothing

**Message:** *"(no relevant transcripts found)"*

This is not an error.  Commit and PR messages are generated from the diff
and CONTEXT.md alone.  Transcripts are optional enrichment.

This happens when:
- You have not had any Cursor agent chats yet.
- The chat transcripts do not contain identifiers from your diff.
- The transcripts directory is empty or misconfigured.

The skills proceed normally without chat context.

---

### Kickoff says "No git repository found"

**Error:** *"No git repository found. Initialize with `git init` first."*

Both skills require a git repository.  Initialize one:

```bash
git init
git remote add origin <your-repo-url>
```

Or open a different directory that already contains a `.git/` folder.

---

### Ship skips a phase unexpectedly

If `/ship` skips a phase you expected to run:

1. Check your wording — the intent parser maps keywords to phases.
   Use explicit terms: "implement", "test", "commit", "review", "pr".
2. Run `/ship` with no extra text for the full pipeline.
3. Check CONTEXT.md Progress — if a phase checkbox is already checked,
   the agent may consider it done (currently it re-runs regardless, but
   future versions may skip completed phases).

---

### Sensitive files detected during staging

**Warning:** *"Skipping sensitive file: `<path>`. Stage manually if intended."*

Ship Phase 3 never auto-stages files matching `.env*`, `*credentials*`,
`*secret*`, `*.pem`, `*.key`, or `*token*`.

If the file is safe to commit (e.g. a token configuration template):

```bash
git add <file>    # Stage manually
/ship commit      # Then commit
```
