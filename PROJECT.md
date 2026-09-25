# CNAT legacy signature generator

Shared starting point for Codex and Claude Code. This file holds current workflow facts; preserve the detailed references below.

## Source and release
- Source: this repository root, including a dedicated worktree of it.
- Repository: `https://github.com/iambradass/sig-generator.git`.
- Release: Existing GitHub/Vercel integration. Verify target project and production branch before any authorized release.
- This older static signature generator and its Stripe API are separate from cnat-signature-builder. Preserve existing uncommitted API, page, and package changes. Do not create payments or invoke checkout endpoints as a connectivity test.

## Verify the requested change
- Run `python3 .agent-workflow/verify.py`; use `--base <reviewed-base>` when the change includes commits, or `--checks-only` to run native checks.
- The exact reviewed commands are in `.agent-workflow/checks.json`; `--list` shows coverage. Missing prerequisites and existing failures must be reported, not silently skipped.
- For changed web behavior, check the actual flow at 375px and desktop. For generated reports/documents, inspect the rendered output. Syntax or unit checks alone do not prove visual or live integration behavior.
- Generate required build assets/cache versions before final release checks. After an authorized release, verify the deployed revision and relevant live behavior. Preserve unrelated staged/unstaged work; do not stage everything.

## Continue across sessions
Read `.agent-workflow/STATUS.md` when resuming. Update it after meaningful work with outcomes, validation, remaining steps, and actual deployment state. It points to earlier handoffs; it does not replace them. Current user instructions and verified current state govern over dated notes.

## Detailed context, only as needed
- `vercel.json`
- `package.json`
