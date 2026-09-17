#!/usr/bin/env bash
# Pull a bench app from git inside the running tncv2 bench, migrate, restart.
#
# Lives in the repo so it is reviewable and versioned, but it RUNS on the Dokploy
# host. Install it there with:
#   sudo install -m 0755 -o root -g root deploy-tnc-app.sh /usr/local/bin/deploy-tnc-app.sh
#
# Invoked over SSH by .github/workflows/deploy.yml. Safe to run by hand.
#
# Why not Dokploy's own auto-deploy webhook: that triggers a compose redeploy, and
# (a) the bootstrap script skips any app whose folder already exists, so it never
# pulls, and (b) `docker compose up -d` with an unchanged compose file does not
# recreate containers at all, so the entrypoint never re-runs. The app code lives
# on a volume, one layer below what Dokploy manages.
set -euo pipefail

#   deploy-tnc-app.sh <app> [branch] [stack] [site]
#
# Stack and site default to the tncv2 bench so existing callers keep working.
# Pass them to deploy the same app to another Dokploy project on this server -
# an app is often installed on several benches, and each needs its own target.
APP="${1:-tnc_v2_360ithub}"
BRANCH="${2:-360ithub_master}"
STACK="${3:-test-demo-erpnext-w6y5gf}"
SITE="${4:-tncv2.360ithub.com}"
WEB="$STACK-web-1"

if [ "$(docker inspect -f '{{.State.Running}}' "$WEB" 2>/dev/null)" != "true" ]; then
	echo "FATAL: container $WEB is not running" >&2
	exit 1
fi

echo "==> $APP @ $SITE: pulling $BRANCH inside $WEB"
docker exec -i "$WEB" bash -s <<EOF
set -euo pipefail
cd "/home/frappe/frappe-bench/apps/$APP"

# developer_mode is on, so frappe exports doctype JSON straight into the app
# folder. A dirty tree here is usually someone's unsaved work on the server -
# refuse rather than clobber it. Commit/stash on the box, then re-run.
if [ -n "\$(git status --porcelain)" ]; then
	echo "FATAL: $APP has uncommitted changes on the server:" >&2
	git status --short >&2
	exit 1
fi

# bench get-app names the remote "upstream", not "origin". Read whatever the
# branch actually tracks and fall back to the first remote, so this works for
# any app in the bench regardless of how it was fetched.
remote=\$(git config --get "branch.$BRANCH.remote" || true)
[ -n "\$remote" ] || remote=\$(git remote | head -1)
if [ -z "\$remote" ]; then
	echo "FATAL: $APP has no git remote configured" >&2
	exit 1
fi
echo "    remote: \$remote"

before=\$(git rev-parse HEAD)
git fetch --prune "\$remote"
git checkout "$BRANCH"
git pull --ff-only "\$remote" "$BRANCH"
after=\$(git rev-parse HEAD)

if [ "\$before" = "\$after" ]; then
	echo "    already at \$(git log -1 --oneline) - nothing to pull"
else
	git log --oneline "\$before..\$after"
fi

cd /home/frappe/frappe-bench

# bench migrate prints a progress bar line per percent per app - thousands of \r
# lines. Left unfiltered they flood the CI log and everything after them gets
# truncated, so a healthy deploy looks like it hung at "Updating DocTypes 100%".
# Capture instead, then print only the lines worth reading. On failure dump the
# tail so the traceback survives.
log=/tmp/migrate-\$\$.log
if ! bench --site "$SITE" migrate > "\$log" 2>&1; then
	echo "FATAL: bench migrate failed on $SITE:" >&2
	grep -vE '\] +[0-9]{1,3}%\$' "\$log" | tail -60 >&2
	rm -f "\$log"
	exit 1
fi
grep -vE '\] +[0-9]{1,3}%\$|^[[:space:]]*\$' "\$log" | tail -20
rm -f "\$log"

bench --site "$SITE" clear-cache
EOF

# bench serve holds Python in memory, and worker/scheduler never reload at all.
# Assets are left to the watch container, which is already running bench watch.
echo "==> restarting web, worker, scheduler"
docker restart "$STACK-web-1" "$STACK-worker-1" "$STACK-scheduler-1" >/dev/null

echo "==> waiting for the site to answer"
for _ in $(seq 1 30); do
	# -S is deliberately absent: the first probes get a 502 while bench serve
	# boots, and printing those makes a healthy deploy look like a failed one.
	if curl -fs -o /dev/null -m 5 "https://$SITE/api/method/ping"; then
		echo "==> deployed $APP@$BRANCH to $SITE - site is up"
		exit 0
	fi
	sleep 5
done

echo "FATAL: $SITE did not answer within 150s. Check: docker logs --tail 100 $WEB" >&2
exit 1
