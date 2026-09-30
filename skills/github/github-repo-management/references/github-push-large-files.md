# GitHub Push Failures: Large Files & History Rewrite

## Problem: GH001 — Large File Exceeds 100 MB Limit

GitHub rejects pushes where **any object in history** (not just the current commit) exceeds 100 MB, even if the file has been deleted in the current branch.

**Error:**
```
remote: error: File state.db is 100.11 MB; this exceeds GitHub's file size limit of 100.00 MB
remote: error: GH001: Large files detected.
! [remote rejected] main -> main (pre-receive hook declined)
```

**Why this is confusing:** The file was already removed in the current commit, so `git status` looks clean. But if any prior commit in the history still references the blob, GitHub rejects the entire push.

---

## Prevention: Always .gitignore Binary Database Files

SQLite databases, WAL journals, and similar binary state files should never be in git:

```bash
# Add to .gitignore before staging
echo -e "*.db\n*.db-shm\n*.db-wal\n*.sqlite\n*.sqlite3" >> .gitignore
git add .gitignore
git commit -m "chore: ignore binary database files"
```

---

## Fix: Remove Large File from Entire History

When push is blocked because a large file exists in history, rewrite history to remove it, then force-push. `git-filter-repo` is the right tool (available via `pip install git-filter-repo`).

### Step-by-Step

**1. Identify the problematic paths:**
```bash
git status                    # may show file already removed locally
git log --oneline --all | grep state.db  # check if it's in history
```

**2. Install git-filter-repo if needed:**
```bash
pip install git-filter-repo -q
```

**3. Rewrite history to remove the file from all branches and tags:**
```bash
git filter-repo --invert-paths --path state.db --path state.db-shm --path state.db-wal --force
```

> ⚠️ **Warning:** `filter-repo` removes the `origin` remote (it warns about this). You must re-add it after.

**4. Re-add the origin remote:**
```bash
git remote add origin https://ghp_TOKEN@github.com/owner/repo.git
# Or if it still exists (check with git remote -v):
git remote set-url origin https://ghp_TOKEN@github.com/owner/repo.git
```

**5. Force-push to overwrite remote history:**
```bash
git push origin main --force
```

**6. Verify the push succeeded and the file is gone:**
```bash
git ls-files | grep state.db   # should be empty
git log --oneline -3            # should show clean history without the file
```

---

## Pattern: Check Before Pushing (Pre-flight)

Before any `git push` that might fail on a large file, especially in a cron job:

```bash
# Quick large-file check in current branch
git ls-files | while read f; do
  size=$(git cat-file -s "HEAD:$f" 2>/dev/null || echo 0)
  if [ "$size" -gt 90000000 ]; then
    echo "LARGE: $f ($(numfmt --to=iec $size))"
  fi
done
```

Or check against GitHub's 100 MB limit before push:
```bash
# Check if any file in HEAD exceeds 90 MB
git ls-tree -r --long HEAD | awk '$3 > 90000000 {print $3, $4, $5}'
```

---

## Alternative: git filter-branch (if filter-repo unavailable)

If `git-filter-repo` cannot be installed, `git filter-branch` works but is slower and requires clean working tree:

```bash
git rm --cached -f state.db state.db-shm state.db-wal
echo -e "state.db\nstate.db-shm\nstate.db-wal" >> .gitignore
git add .gitignore
git commit -m "Remove large state.db from git tracking"

# This requires working tree to be clean
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch state.db state.db-shm state.db-wal' \
  --prune-empty --tag-name-filter cat -- --all
```

`filter-branch` is deprecated in favor of `filter-repo` — prefer `filter-repo` when available.

---

## Key Insight

| Situation | Solution |
|-----------|----------|
| File staged, not yet committed | `git rm --cached -f <file>` then commit |
| File committed, not yet pushed | Normal commit + push works |
| File in history, push rejected | Rewrite history with `filter-repo --invert-paths`, then force-push |
| Want to prevent this | Add binary file patterns to `.gitignore` before staging |

**Always force-push after history rewrite** — the remote still has the old history and will reject a normal push.
