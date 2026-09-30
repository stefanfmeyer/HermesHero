---
name: git-crypt-skills-migration
description: How to migrate skills from git-crypt encrypted repos to new locations, including key extraction and decryption
version: 1.0.0
author: Hermes Agent
tags: [git, git-crypt, skills, migration]
---

# Migrating git-crypt Encrypted Skills

## Problem

Skills copied from a git-crypt encrypted repo (like OpenClaw's) arrive as encrypted binary files that can't be read.

## How to Diagnose

Read first 20 bytes of SKILL.md:
```bash
head -c 20 ~/.hermes/skills/skill-name/SKILL.md | xxd
# Encrypted: starts with 0047 4954 4352 595054 (null + GITCRYPT)
# Readable: starts with 2d 2d 2d (--- yaml frontmatter)
```

Python check:
```python
with open('SKILL.md', 'rb') as f:
    header = f.read(20)
if header.startswith(b'\x00GITCRYPT'):
    print("ENCRYPTED")
```

## Finding the Key

1. Check `~/.openclaw-keys/` — OpenClaw stores keys here
2. Check source repo: `<repo>/.git/git-crypt/keys/default`
3. Keys are identical across repos if they share the same encryption

## Extracting the Raw AES Key from OpenClaw Key File

The `.openclaw-keys/openstef.key` format:
```
\x00 + "GITCRYPTKEY" + nulls + version + nulls + type + nulls + 32-byte AES key
```

Extract with Python:
```python
key_bytes = open('/path/to/key', 'rb').read()
# Find the GITCRYPTKEY header
idx = key_bytes.find(b'GITCRYPTKEY')
# Skip header + nulls + version (4 bytes) + nulls + type (1 byte) + nulls
# Raw key starts at offset ~36, length 32 bytes
actual_key = key_bytes[36:68]
```

## Decrypting

```bash
cd ~/.hermes/skills
git-crypt unlock /path/to/key  # If key matches

# Or if gpg-based git-crypt:
git-crypt unlock  # stdin with key data
```

## Critical Limitation

**git-crypt encrypts git objects, not just files.** Even after `git-crypt unlock` or removing the filter:
- If git objects were encrypted before copying, they remain encrypted in the new repo
- `git checkout -- .` restores encrypted versions from git objects
- Removing `.git/git-crypt/` doesn't decrypt — only re-encrypts with new key

## Practical Workflow

1. In source repo: `git-crypt unlock` with correct key
2. Copy files to destination
3. In destination: either git-crypt is initialized with same key, OR files are now plaintext

If key doesn't match:
- Scan source for unencrypted files before copying
- Look for pre-encryption backups in git history
- Ask user for unencrypted copies
