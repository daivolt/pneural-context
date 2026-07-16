# Branch Protection Rules

Configure these in GitHub → Settings → Branches → Branch protection rules → `main`.

## Required rules

| Rule | Setting |
|------|---------|
| Require PR before merging | ✅ Enabled |
| Require approvals | 1 approval minimum |
| Dismiss stale reviews on push | ✅ Enabled |
| Require status checks | ✅ Enabled |
| Required checks | `lint`, `typecheck`, `test` |
| Require branches to be up to date | ✅ Enabled |
| Require conversation resolution | ✅ Enabled |
| Require signed commits | ❌ Disabled (optional) |
| Require linear history | ❌ Disabled (optional) |

## Required status checks

These must pass before merging:

1. **lint** — ruff check + ruff format check
2. **typecheck** — mypy pneural_context/ with 0 errors
3. **test (3.12)** — pytest with ≥70% coverage gate

## Recommended branch naming

- `feat/short-description` — new features
- `fix/short-description` — bug fixes
- `refactor/short-description` — code restructuring
- `test/short-description` — test additions
- `ci/short-description` — CI/CD changes
