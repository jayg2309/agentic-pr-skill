---
name: commit
description: >-
  Generate a FreeIPA-style commit message from staged changes and Cursor
  agent chat context, then commit with human approval.  Use when the user
  wants to commit changes, write a commit message, review staged work, or
  asks to summarize and commit code in the current repository.
trusted_scripts:
  - ../shared/transcript_helper.py
---

# Commit Skill

> **Autonomy rule:** Run ALL shell commands (git, python, curl) immediately
> and silently.  Do NOT ask the user for permission to run any command.
> The ONLY point where the user is consulted is the commit message
> approval gate in Step 4.  Everything else is automatic.

Follow these steps **in order**. Do not skip or reorder any step.

## Step 0 — Resolve runtime parameters

All values MUST be determined at runtime — never hardcode paths or names.
Run every command in this step silently — do NOT ask the user for approval.

> **Permissions:** Any `gh` command in this skill MUST be run with
> `required_permissions: ["all"]` so the sandbox does not block GitHub
> API calls.  Without this, the sandbox strips the auth token and `gh`
> falsely reports "Requires authentication".

1. **repo_path** — From the system `<user_info>` block, read the `Workspace Path`.
   If a git repository directory exists inside the workspace (e.g. `freeipa/` or
   `freeipa-webui/`), use the sub-directory that contains uncommitted changes.
   If the workspace root itself is a git repo, use that.  If multiple sub-repos
   have changes and the choice is ambiguous, ask the user which one to use.

2. **base_branch** — Run silently (do not ask the user):
   ```
   git -C <repo_path> symbolic-ref refs/remotes/origin/HEAD 2>/dev/null \
     | sed 's|refs/remotes/origin/||'
   ```
   Use the result (e.g. `main` or `master`).  If the command fails, silently
   fall back to `master`.

3. **author_name / author_email / github_email** — Resolve fresh each time
   (no caching; these are fast local/API calls):

   ```bash
   AUTHOR_NAME="$(git -C <repo_path> config user.name)"
   AUTHOR_EMAIL="$(git -C <repo_path> config user.email)"
   GITHUB_EMAIL="$(gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"' 2>/dev/null || echo "$AUTHOR_EMAIL")"
   ```

   - Use `GITHUB_EMAIL` as the commit **author email** (so commits link
     to the GitHub profile).
   - Use `AUTHOR_EMAIL` only in the `Signed-off-by` trailer.

4. **transcripts_dir** — Read the path from the system `<agent_transcripts>` tag
   (the folder containing `.jsonl` chat files).

5. **issue_url** — Include only if the user supplies one (e.g. "commit, fixes
   https://pagure.io/freeipa/issue/1234").

---

## Step 1 — Precondition check

Run inside **repo_path**:

```
git status --porcelain
```

Interpret the output:

| Situation | Action |
|---|---|
| **Staged AND unstaged/untracked changes both exist** | STOP. List the unstaged files and ask the user: *"You have unstaged changes in: [file list]. What would you like to do? (a) Stage all changes (b) Keep only what's already staged (c) Abort"*. Wait for the user's reply before continuing. If (a), run `git add -A`. If (c), abort. |
| **Only staged changes** | Proceed to Step 2. |
| **Only unstaged/untracked changes (nothing staged)** | Tell the user: *"Nothing is staged. Run `git add <files>` first, or tell me which files to stage."* Then stop. |
| **Clean working tree** | Tell the user: *"Working tree is clean — nothing to commit."* Then stop. |

---

## Step 2 — Gather diff and context

Run all three commands inside **repo_path** and collect their output:

1. **Staged diff:**
   ```
   git diff --staged
   ```

2. **Recent commit log** (for surrounding context):
   ```
   git log --oneline -10
   ```

3. **Transcript scoring** — pipe the staged diff into the shared helper:
   ```
   git diff --staged | python3 .cursor/skills/shared/transcript_helper.py --top-n 3
   ```
   The script prints the top-scoring transcript excerpts.  If it prints
   "(no relevant transcripts found)", proceed without chat context.

Combine these three outputs as your context for the next step.

---

## Step 3 — Synthesize the commit message

Using the staged diff, recent log, and transcript excerpts, generate a single
commit message following this structure:

### Title line (max 72 characters)

```
<component>: <short imperative description>
```

- If the change is scoped to one component, prefix with that component name
  in lowercase (e.g. `webui:`, `ipatests:`, `ipa-kdb:`).
- If cross-cutting, omit the prefix and start with a capitalized verb.
- Imperative mood. No trailing period.

### Body (blank line after the title)

- One or more bullet lines:
  ```
  - <what changed>
  - <why it changed — use the agent chat context if it reveals intent>
  ```
- Be specific: reference actual function names, class names, file paths.
- Do NOT invent motivation.  If the chat context does not clearly relate to
  the diff, base the message entirely on the diff.

### Trailers (each on its own line, blank line before this block)

Include whichever apply, in this order:

1. `Fixes: https://pagure.io/freeipa/issue/NNNN` — only if an issue URL was
   provided or clearly identifiable from the context.
2. `Assisted-by: Claude <noreply@anthropic.com>`
3. `Signed-off-by: <AUTHOR_NAME> <<AUTHOR_EMAIL>>` — use the values from
   `git config user.name` and `git config user.email` (NOT the GitHub
   noreply email).

### Present the message

Show the complete commit message to the user inside a fenced code block so
they can review it clearly.

---

## Step 4 — Human approval gate (mandatory — do NOT skip)

Ask the user exactly:

> **Ready to commit with this message?  y / e / n**

Wait for the user's response.

| Reply | Action |
|---|---|
| **y** | Proceed to Step 5 immediately. |
| **e** | The user's **very next message** IS the edited commit message. Do NOT prompt them with "Please provide your modified message" or any other intermediate reply — just wait for their next message. Once received, **commit immediately** using that exact message — go straight to Step 5. **ABSOLUTELY NO re-confirmation, no "Ready to commit?", no second approval gate.** The edit IS the approval. |
| **n** | Print *"Commit aborted — no changes were made."* and stop. |

---

## Step 5 — Execute the commit

Use low-level git plumbing (`git commit-tree`) to create the commit.
This bypasses any IDE-injected hooks or trailers (e.g. Cursor's
`Made-with:` trailer) that `git commit` cannot avoid even with
`--no-verify`.

Run inside **repo_path**:

```bash
# 1. Capture the tree, parent, and author identity
TREE=$(git write-tree)
PARENT=$(git rev-parse HEAD)
AUTHOR_NAME="$(git config user.name)"
AUTHOR_EMAIL="$(git config user.email)"
GITHUB_EMAIL="$(gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"' 2>/dev/null || echo "$AUTHOR_EMAIL")"

# 2. Create the commit object with the approved message
NEW_COMMIT=$(
  GIT_AUTHOR_NAME="$AUTHOR_NAME" \
  GIT_AUTHOR_EMAIL="$GITHUB_EMAIL" \
  GIT_COMMITTER_NAME="$AUTHOR_NAME" \
  GIT_COMMITTER_EMAIL="$GITHUB_EMAIL" \
  git commit-tree "$TREE" -p "$PARENT" <<'EOF'
<full commit message here>
EOF
)

# 3. Point the branch at the new commit
BRANCH=$(git branch --show-current)
git update-ref "refs/heads/$BRANCH" "$NEW_COMMIT"
git reset --hard "$NEW_COMMIT"
```

### Post-commit verification

After the commit succeeds, verify the message is clean:

```bash
git log -1 --format='%B' HEAD
```

Confirm the message matches what was approved — no extra trailers
(e.g. `Made-with:`) were injected.  If an unwanted trailer appears,
warn the user.

Print:

- The resulting commit hash (from `git rev-parse --short HEAD`).
- A confirmation line: *"Committed successfully."*

If any step fails, show the error output to the user and stop.
