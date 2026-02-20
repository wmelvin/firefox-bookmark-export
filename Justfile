@default:
  @just --list

# Run pyproject-build
@build: check lint test
  uv build

#  Run ruff format --check
@check:
  uv run ruff format --check

# Run check, lint, and test
@checks: check lint test

# Remove dist and egg-info
@clean:
  -rm dist/*
  -rm fbx.egg-info/*

# Run ruff format
@format:
  uv run ruff format

# Redirect 'fbx -h' to temp.txt
@help:
  uv run fbx -h > temp.txt


# Run ruff check
@lint:
  uv run ruff check

# Run pytest
@test:
  uv run pytest
