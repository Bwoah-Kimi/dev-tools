#!/usr/bin/env bash
# Generate a review package: commit list, stat summary, and the net diff
# with extended context, written to a file the reviewer reads in one call.
#
# Usage: review_package.sh BASE HEAD ISSUE_NUMBER OUTPUT_ROOT
# Output: OUTPUT_ROOT/review/ISSUE_NUMBER/diff-<base7>..<head7>.diff
set -euo pipefail

if [ $# -ne 4 ]; then
  echo "usage: review_package.sh BASE HEAD ISSUE_NUMBER OUTPUT_ROOT" >&2
  exit 2
fi

base=$1
head=$2
issue=$3
output_root=$4

git rev-parse --verify --quiet "$base" >/dev/null || { echo "bad BASE: $base" >&2; exit 2; }
git rev-parse --verify --quiet "$head" >/dev/null || { echo "bad HEAD: $head" >&2; exit 2; }

dir="${output_root}/review/${issue}"
mkdir -p "$dir"
out="${dir}/diff-$(git rev-parse --short "$base")..$(git rev-parse --short "$head").diff"

{
  echo "# Review package: ${base}..${head}"
  echo
  echo "## Commits"
  git log --oneline "${base}..${head}"
  echo
  echo "## Files changed"
  git diff --stat "${base}..${head}"
  echo
  echo "## Diff"
  git diff -U10 "${base}..${head}"
} > "$out"

commits=$(git rev-list --count "${base}..${head}")
echo "wrote ${out}: ${commits} commit(s), $(wc -c < "$out" | tr -d ' ') bytes"
