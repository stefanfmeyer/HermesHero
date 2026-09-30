---
name: selective-text-revert
description: Restore specific wording/text from a past commit without reverting everything. Use when a commit changed N files but you only want back some of the wording while keeping newer changes.
---

# Selective Text Revert

Restore specific wording/text from a past commit without reverting everything in that commit.

## When to Use

- A commit changed N files, but you only want to restore the wording/text in some of them
- You want to keep newer changes that came after the commit
- Typical case: reverted "open-source" wording but kept new pricing structure

## Method

### Step 1: Find the commit
```bash
git log --oneline -30  # find the commit that removed/changed wording
# e.g. commit 1334858 "chore: remove all open-source references, close source code"
```

### Step 2: See what the commit changed
```bash
git show <commit> --stat          # list of all changed files
git diff <commit>^..<commit>       # full diff to see what was removed
```

### Step 3: Extract pre-change versions for reference
```bash
git show <commit>^:<filepath> > /tmp/old_file.txt   # extract to temp for reading
git checkout <commit>^ -- <filepath>                     # restore file as it was before commit (for deleted files)
```

### Step 4: Apply targeted patches
For each file that needs restoring:
1. Read the current file
2. Identify exact strings that differ using the diff from Step 2
3. Use `patch(old_string, new_string)` to restore wording
4. Keep any NEW changes that are unrelated (e.g., new pricing cards, new features)

### Step 5: Verify build before committing
```bash
npm run build   # type check before commit
```

## Key Principle

**Wholesale `git revert` vs. selective patch:**
- `git revert <commit>` reverts ALL changes in that commit — often too much
- Targeted patches let you restore only the specific text you want, preserving newer additions

## Example: Restoring open-source wording

The commit `1334858` changed 22 files — some we wanted back (AGPL wording, open-source page, license file) and some we didn't (pricing structure changes, new features).

Instead of reverting the whole commit:
1. Restored `LICENSE` directly from pre-commit state
2. Restored deleted files (`open-source.md`, `overview.md`, `contributions.md`, `app/(public)/open-source/page.tsx`) with `git checkout`
3. Patched each affected file individually — restoring only the open-source text references
4. Kept the new Starter($29)/Pro($59) pricing card structure intact

## Gotchas

- Always verify build (`npm run build`) after patching — imports can get dropped during manual editing
- If a file had imports added/removed that you don't want, check `git show <commit>^:<filepath>` carefully
- For deleted files, `git checkout <commit>^ -- <filepath>` restores them cleanly
