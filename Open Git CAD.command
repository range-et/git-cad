#!/bin/zsh
cd "${0:A:h}"
if [[ ! -x .venv/bin/git-cad ]]; then
  echo "Install first: uv sync --extra dev --extra mcp"
  exit 1
fi
if [[ ! -f demo-project/cadgit.json ]]; then
  .venv/bin/git-cad demo demo-project
fi
exec .venv/bin/git-cad --project demo-project ui
