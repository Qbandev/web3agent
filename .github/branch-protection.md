# Branch Protection Rules for web3agent

## Recommended Settings for `main` branch

Go to: **Settings → Branches → Add rule** (pattern: `main`)

### ✅ Enable These Rules

| Rule | Setting | Reason |
|------|---------|--------|
| **Require pull request reviews** | 0 reviews (solo dev) | Can increase to 1+ for teams |
| **Require status checks to pass** | ✅ Enable | Block merge if CI fails |
| **Required checks** | `build-and-test` | From ci.yml workflow |
| **Require branches to be up to date** | ✅ Enable | Prevent merge conflicts |
| **Require signed commits** | ✅ Enable | Already using GPG signing |
| **Include administrators** | ✅ Enable | Rules apply to everyone |
| **Restrict deletions** | ✅ Enable | Prevent accidental main deletion |

### ❌ Skip These (for solo dev)

| Rule | Reason |
|------|--------|
| Require conversation resolution | Not needed for solo |
| Require linear history | Squash merge handles this |
| Lock branch | Would block all changes |

## How to Apply

### Via GitHub CLI:
```bash
gh api repos/Qbandev/web3agent/branches/main/protection \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -f required_status_checks='{"strict":true,"contexts":["build-and-test"]}' \
  -f enforce_admins=true \
  -f required_pull_request_reviews=null \
  -f restrictions=null \
  -F allow_force_pushes=false \
  -F allow_deletions=false
```

### Via Web UI:
1. Go to https://github.com/Qbandev/web3agent/settings/branches
2. Click "Add branch protection rule"
3. Branch name pattern: `main`
4. Configure as above
5. Save changes

## CI Workflow Requirements

Ensure your CI workflow has a job named `build-and-test` for the status check:

```yaml
jobs:
  build-and-test:  # This name must match the required check
    runs-on: ubuntu-latest
    # ...
```

