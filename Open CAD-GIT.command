#!/bin/zsh
cd "${0:A:h}"
if [[ ! -x .venv/bin/cad-git ]]; then
  echo "Install first: uv sync --extra dev --extra mcp"
  exit 1
fi
if [[ ! -f demo-project/cadgit.json ]]; then
  .venv/bin/cad-git demo demo-project
fi
exec .venv/bin/cad-git --project demo-project ui
