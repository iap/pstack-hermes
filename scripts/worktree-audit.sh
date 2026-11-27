#!/usr/bin/env bash
# Read-only worktree prune audit. Classifies every git worktree by size, merge
# state, uncommitted work, remote/PR state, and the most recent chat that
# operated in it. Emits a table sorted by size with a suggested bucket. Never
# deletes anything; deletion stays a human-gated step in the playbook.
#
# Usage: worktree-audit.sh [repo-path]   (defaults to the current repo)
set -u

# F10-F12 fix: GNU coreutils vs BSD/macOS mtime + epoch conversion.
if stat -c '%Y' / >/dev/null 2>&1; then
	stat_mtime() { stat -c '%Y' "$1" 2>/dev/null; }
else
	stat_mtime() { stat -f '%m' "$1" 2>/dev/null; }
fi
# Epoch probe: GNU date prints the epoch itself for -d @0 ('0'); BSD date's
# -d flag means something unrelated (kernel DST), so it never prints '0'.
# A plain exit-status probe on '-d @0' is NOT safe: BSD date may accept it.
if [ "$(date -d @0 '+%s' 2>/dev/null)" = "0" ]; then
	date_epoch() { date -d "@$1" '+%Y-%m-%d' 2>/dev/null; }
else
	date_epoch() { date -r "$1" '+%Y-%m-%d' 2>/dev/null; }
fi

repo="${1:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$repo" ] && { echo "not in a git repo; pass a repo path" >&2; exit 1; }
cd "$repo" || exit 1

# Main worktree is the first entry; everything else is a candidate.
main_wt=$(git worktree list --porcelain | awk '/^worktree /{print substr($0, 10); exit}')

# The remote default branch drives the merge check. Use the main worktree's
# upstream only when that branch is its remote's default, so a checked-out
# feature branch cannot select the wrong trunk remote. Both network steps are
# best-effort so the audit still works offline.
main_branch=$(git -C "$main_wt" symbolic-ref --quiet --short HEAD 2>/dev/null)
candidate_remote=$(git -C "$main_wt" config --get "branch.$main_branch.remote" 2>/dev/null || true)
candidate_merge=$(git -C "$main_wt" config --get "branch.$main_branch.merge" 2>/dev/null || true)
default_remote=""
if [ -n "$candidate_remote" ] && [ "$candidate_remote" != "." ]; then
	git -C "$main_wt" fetch "$candidate_remote" --quiet 2>/dev/null || true
	git -C "$main_wt" remote set-head "$candidate_remote" --auto >/dev/null 2>&1 || true
	candidate_head=$(git -C "$main_wt" symbolic-ref --quiet "refs/remotes/$candidate_remote/HEAD" 2>/dev/null || true)
	if [ -n "$candidate_head" ] && [ "$candidate_head" = "refs/remotes/$candidate_remote/${candidate_merge#refs/heads/}" ]; then
		default_remote=$candidate_remote
	fi
fi
[ -z "$default_remote" ] && default_remote=$(git -C "$main_wt" remote 2>/dev/null | sed -n '1p')
[ -z "$default_remote" ] && default_remote=origin
fetched_remotes="$default_remote"
git fetch "$default_remote" --quiet 2>/dev/null || echo "warn: could not fetch $default_remote; merged and pushed columns may be stale" >&2
trunk=""
if git remote set-head "$default_remote" --auto >/dev/null 2>&1; then
	trunk_ref=$(git symbolic-ref --quiet --short "refs/remotes/$default_remote/HEAD" 2>/dev/null || true)
	trunk=${trunk_ref#"$default_remote/"}
else
	remote_head=$(git ls-remote --symref "$default_remote" HEAD 2>/dev/null | awk '$1 == "ref:" { print $2; exit }')
	trunk=${remote_head#refs/heads/}
fi
if [ -z "$trunk" ]; then
	echo "warn: remote default branch unknown; merged column unavailable" >&2
else
	git fetch "$default_remote" "+refs/heads/$trunk:refs/remotes/$default_remote/$trunk" --quiet 2>/dev/null || echo "warn: could not fetch $default_remote/$trunk; merged column may be stale" >&2
fi

# PR state by branch, fetched once. Empty if gh is unavailable.
prs=$(mktemp)
gh pr list --author "@me" --state all --limit 1000 \
	--json number,state,headRefName 2>/dev/null > "$prs" || echo "[]" > "$prs"

# Transcripts dir: ~/.cursor/projects/<slugified-repo-path>/agent-transcripts (Cursor-specific; on hermes, sessions live in SQLite and this check skips gracefully).
slug=$(printf '%s' "$main_wt" | sed 's#^/##; s#/#-#g')
transcripts="$HOME/.cursor/projects/$slug/agent-transcripts"
now=$(date +%s)

printf "SIZE\tAGE\tMERGED\tDIRTY\tREMOTE\tPR\tLAST_CHAT\tBUCKET\tWORKTREE\n"

git worktree list --porcelain | awk '/^worktree /{print substr($0, 10)}' | while read -r wt; do
	[ "$wt" = "$main_wt" ] && continue

	size=$(du -sh "$wt" 2>/dev/null | awk '{print $1}')
	head=$(git -C "$wt" rev-parse HEAD 2>/dev/null)
	head_ts=$(git -C "$wt" log -1 --format='%ct' HEAD 2>/dev/null || echo 0)
	age=$([ "$head_ts" -gt 0 ] 2>/dev/null && echo "$(( (now - head_ts) / 86400 ))d" || echo "?")

	# Squash-merged branches are not ancestors of the trunk, so PR state is the
	# real signal; merge-base only catches fast-forward/rebase merges.
	if [ -z "$trunk" ]; then merged=unknown
	elif git merge-base --is-ancestor "$head" "refs/remotes/$default_remote/$trunk" 2>/dev/null; then merged=YES
	else merged=no; fi

	# Distinguish real WIP (tracked edits) from disposable untracked scratch.
	porcelain=$(git -C "$wt" status --porcelain 2>/dev/null)
	if [ -z "$porcelain" ]; then dirty=clean
	elif printf '%s\n' "$porcelain" | grep -qv '^??'; then
		dirty="wip:$(printf '%s\n' "$porcelain" | grep -cv '^??')"
	else dirty="scratch:$(printf '%s\n' "$porcelain" | grep -c '^??')"; fi

	branch=$(git -C "$wt" symbolic-ref --quiet --short HEAD 2>/dev/null || echo "")
	push_remote=$(git -C "$wt" config --get "branch.$branch.remote" 2>/dev/null || true)
	local_upstream=no
	[ "$push_remote" = "." ] && { push_remote=""; local_upstream=yes; }
	[ -z "$push_remote" ] && push_remote=$default_remote
	merge_ref=$(git -C "$wt" config --get "branch.$branch.merge" 2>/dev/null || true)
	[ "$local_upstream" = yes ] && merge_ref=""
	compare_ref="$push_remote/$branch"
	if [ -n "$merge_ref" ] && [ -n "$push_remote" ]; then
		compare_ref="$push_remote/${merge_ref#refs/heads/}"
	fi
	if ! printf '%s\n' "$fetched_remotes" | grep -qxF "$push_remote"; then
		git fetch "$push_remote" --quiet 2>/dev/null || echo "warn: could not fetch $push_remote; pushed column may be stale" >&2
		fetched_remotes="$fetched_remotes
$push_remote"
	fi
	if [ -z "$branch" ]; then remote=detached
	elif git -C "$wt" show-ref --verify --quiet "refs/remotes/$compare_ref"; then
		[ "$(git -C "$wt" rev-parse "refs/remotes/$compare_ref" 2>/dev/null)" = "$head" ] \
			&& remote=pushed \
			|| remote="ahead$(git -C "$wt" rev-list --count "refs/remotes/$compare_ref..HEAD" 2>/dev/null)"
	else remote=no-remote; fi

	pr=$([ -n "$branch" ] && jq -r --arg b "$branch" \
		'.[] | select(.headRefName==$b) | "#\(.number)/\(.state)"' "$prs" 2>/dev/null | head -1)
	[ -z "$pr" ] && pr="-"

	# Most recent chat whose transcript operated in this worktree. Match path
	# followed by "/" or a quote so glint-482 does not match glint-482-r37.
	last="-"; last_ts=0
	if [ -d "$transcripts" ]; then
		f=$(rg -l -e "${wt}/" -e "${wt}\"" "$transcripts" 2>/dev/null \
			| while IFS= read -r tfile; do mt=$(stat_mtime "$tfile"); [ -n "$mt" ] && printf '%s %s\n' "$mt" "$tfile"; done | sort -rn | head -1)
		if [ -n "$f" ]; then last_ts=$(echo "$f" | awk '{print $1}')
			last=$(date_epoch "$last_ts"); fi
	fi
	recent=$([ "$last_ts" -gt 0 ] 2>/dev/null && [ $(( (now - last_ts) / 86400 )) -le 4 ] && echo yes || echo no)

	case "$dirty" in wip:*) bucket=hold-wip ;; *)
		case "$pr" in *OPEN*) bucket=hold-open-pr ;; *)
			if [ "$recent" = yes ]; then bucket=verify-recent-chat
			elif [ "$merged" = YES ] || [ "$pr" != "-" ]; then bucket=safe
			else bucket=review; fi ;;
		esac ;;
	esac

	printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
		"$size" "$age" "$merged" "$dirty" "$remote" "$pr" "$last" "$bucket" "$wt"
done | sort -t$'\t' -k1,1 -rh

rm -f "$prs"
