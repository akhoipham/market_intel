#!/usr/bin/env bash
# Run once, locally, from the repo root. Stops the bleeding.
set -euo pipefail

# 1. Keep your local DB — it is your accumulated history.
cp data/intel.db ~/intel.db.backup
echo "Backed up to ~/intel.db.backup"

# 2. Untrack the oversized generated files (leaves them on disk).
git rm --cached data/intel.db data.json .DS_Store \
  data/tickers.csv data/tickers_sec.json data/marketcap_cache.json 2>/dev/null || true

# 3. Add the .gitignore, then commit and push. This push is small and will succeed.
git add .gitignore .github/workflows/update-dashboard.yml
git commit -m "fix: stop committing generated DB; store snapshot as release asset"
git push

# 4. Seed the release asset with your existing history so nothing is lost.
gh release create data-snapshot --title "Data snapshot" \
  --notes "Rolling intel.db. Replaced on every run; not part of git history." 2>/dev/null || true
gh release upload data-snapshot data/intel.db --clobber
echo "Done. Trigger the workflow manually to confirm: gh workflow run 'Update dashboard'"
