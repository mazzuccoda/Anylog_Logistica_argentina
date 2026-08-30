#!/bin/bash
# SessionStart hook: installs the plugin marketplaces and plugins this project
# relies on, so they're available in every new Claude Code on the web session.
#
# Idempotent by design: `claude plugin marketplace add` and `claude plugin
# install` both no-op successfully when the marketplace/plugin is already
# present, so this script is safe to re-run on every session start.
set -uo pipefail

# Only run in Claude Code on the web (remote) sessions.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

MARKETPLACES=(
  "obra/superpowers-marketplace"
  "spjoshis/claude-code-plugins"
  "aviadr1/claude-code-showcase"
)

# plugin@marketplace pairs to install. Some entries are known to currently be
# broken upstream (missing plugin, invalid manifest) — these are allowed to
# fail without aborting the hook or the session.
PLUGINS=(
  "superpowers@superpowers-marketplace"
  "python-development@cc-plugins"
  "react-development@cc-plugins"
  "testing-patterns@claude-code-showcase"
  "systematic-debugging@claude-code-showcase"
  "pr-review-toolkit@superpowers-marketplace"   # not published in this marketplace as of writing
  "code-review-suite@claude-code-showcase"      # invalid plugin.json (agents field) as of writing
)

echo "[session-start] Adding plugin marketplaces..."
for marketplace in "${MARKETPLACES[@]}"; do
  if claude plugin marketplace add "$marketplace" 2>&1; then
    echo "[session-start] OK: marketplace $marketplace"
  else
    echo "[session-start] WARN: failed to add marketplace $marketplace (continuing)"
  fi
done

echo "[session-start] Installing plugins..."
for plugin in "${PLUGINS[@]}"; do
  if claude plugin install "$plugin" 2>&1; then
    echo "[session-start] OK: plugin $plugin"
  else
    echo "[session-start] SKIP: plugin $plugin unavailable or invalid upstream (non-fatal)"
  fi
done

echo "[session-start] Plugin setup complete."
exit 0
