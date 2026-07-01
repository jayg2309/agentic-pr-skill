# Troubleshooting

### GitHub CLI not found

**Error:** `gh: command not found`

The `gh` CLI is required for PR creation and GitHub email resolution. Install it for your platform:

```bash
# Fedora/RHEL
sudo dnf install gh

# macOS
brew install gh

# Ubuntu/Debian
sudo apt install gh
```

Then authenticate once: `gh auth login`

---

### GitHub authentication failure

**Error:** `gh: Requires authentication` or `HTTP 401`

This usually means `gh` is not logged in, or the Cursor sandbox stripped the auth token.

```bash
# Check current auth status
gh auth status

# Re-authenticate if needed
gh auth login
```

If you see this error *only* when the skill runs (but `gh` works in your terminal), the skill may be missing sandbox permissions. The SKILL.md files already require `required_permissions: ["all"]` for every `gh` command — verify the agent is honoring that.

---

### "Nothing is staged" when running commit

**Error:** *"Nothing is staged. Run `git add <files>` first."*

The commit skill requires at least one staged file. Stage your changes before invoking:

```bash
# Stage specific files
git add src/components/MyComponent.tsx

# Or stage everything
git add -A
```

Then re-run `/commit`.

---

### "Working tree is clean — nothing to commit"

This means there are no changes at all (staged or unstaged). Verify you're in the correct repository directory:

```bash
git status
pwd
```

If you're in a multi-repo workspace, the skill may have picked the wrong sub-directory. Tell the agent which repo to use.

---

### PR skill says "uncommitted changes"

**Error:** *"You have uncommitted changes in: [file list]. Please commit or stash all changes before running the PR skill."*

The PR skill only operates on fully committed code. Resolve with one of:

```bash
# Option 1: Commit everything first (or use the commit skill)
git add -A && git commit -m "WIP"

# Option 2: Stash uncommitted work
git stash

# Then run /pr, and afterwards:
git stash pop
```

---

### Wrong base branch detected

**Error:** The skill targets `master` when it should target `main` (or vice versa).

The skills detect the default branch via `origin/HEAD`. If this is wrong or unset:

```bash
# Auto-detect and set origin/HEAD
git remote set-head origin --auto

# Verify
git symbolic-ref refs/remotes/origin/HEAD
```

---

### Merge conflicts during PR rebase

**Error:** *"There are merge conflicts between your branch and `main`. Please resolve them manually and re-run the PR skill."*

The PR skill automatically aborts the rebase when conflicts are found. Resolve manually:

```bash
# Fetch latest and rebase
git fetch origin main
git rebase origin/main

# Resolve conflicts in each file, then:
git add <resolved-file>
git rebase --continue

# Once clean, re-run /pr
```

---

### Unexpected commits after rebase

**Error:** *"After rebasing, the branch contains unexpected commits: [list]."*

This happens when your fork's default branch has diverged from upstream. Fix by resetting to upstream and cherry-picking your work:

```bash
# Identify your commit hashes first
git log --oneline

# Reset to upstream
git fetch upstream main
git reset --hard upstream/main

# Cherry-pick only your commits
git cherry-pick <commit-hash-1> <commit-hash-2>
```

---

### Wrong author name or email in commits

Commits show an incorrect name or email. The skills read from `git config` on every run, so fix the config:

```bash
# Check current values
git config user.name
git config user.email

# Update if wrong
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

To fix an already-created commit, amend it before pushing:

```bash
git commit --amend --author="Your Name <you@example.com>" --no-edit
```

---

### Commits show "Made-with: Cursor" trailer

Cursor injects this trailer by default. Even though the commit skill uses `git commit-tree` to bypass it, disable the setting to be safe:

```bash
# Check if it's enabled
grep -r "commitMessageTrailer" ~/.config/Cursor/User/settings.json
```

Disable it in Cursor Settings > search `commitMessageTrailer` > uncheck, or add to `settings.json`:

```json
"cursor.chat.commitMessageTrailer": false
```

---

### `git push` fails when creating PR

**Error:** `git push -u origin HEAD` fails.

Common causes and fixes:

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

### "No commits found ahead of base — nothing to PR"

The PR skill found zero commits between your branch and the base branch. Verify:

```bash
# Check what's ahead
git log origin/main..HEAD --oneline

# If empty, you may be on the wrong branch
git branch --show-current
```

---

### Transcript helper finds no relevant transcripts

**Message:** *"(no relevant transcripts found)"*

This is not an error — the skills will still work, just without chat context for the commit message. This happens when:
- You haven't had any Cursor agent chats yet
- The chat transcripts don't contain identifiers related to your diff
- The transcripts directory path is misconfigured

The skill proceeds normally and generates the commit message from the diff alone.

---

### Self-review reports false positives

The guideline check or self-review flags an issue that isn't actually a violation (e.g. a variable that looks unused but is used via reflection, or an import that appears forbidden but is allowed by convention).

This is expected — the review is heuristic, not a linter. When prompted:
- Choose **(b) Proceed anyway** to continue past the finding
- The false positive will appear in the PR body under **Review Notes**, where a human reviewer can dismiss it

If a particular pattern consistently triggers false positives, consider noting it in the PR description so reviewers understand the context.

---

### Self-review blocks on a rule you disagree with

The self-review checks are based on FreeIPA's official contribution guidelines at `skills/shared/freeipa-guidelines.md`. If a rule seems wrong or outdated:

1. Check the upstream documentation to confirm the current convention
2. If the rule in `freeipa-guidelines.md` is outdated, update it to match upstream
3. If you believe the upstream rule should change, raise it on the `freeipa-devel` mailing list

---

### Guidelines file not found

**Error:** The agent can't find `freeipa-guidelines.md`

The skills expect the guidelines file at `.cursor/skills/shared/freeipa-guidelines.md` relative to the repository root. Make sure the skills directory is properly set up:

```bash
ls -la .cursor/skills/shared/freeipa-guidelines.md
```

If missing, re-copy the `skills/` directory from `agentic-pr-skill/` into your workspace's `.cursor/` directory.
