# CI/CD for Frappe Custom Apps on the TNC Bench

**A practical guide.** Push your code to GitHub; two minutes later it is live on the server. No SSH, no manual `git pull`, no `bench migrate` by hand.

Prepared for 360ITHub. Covers the bench at `tncv2.360ithub.com`.

---

## How to use this document

| If you are... | Read |
|---|---|
| New to this and want to understand it | Part 1, then Part 4 |
| Setting up a brand new app | Part 3 (do Part 1 first if unsure) |
| Setting up a brand new server | Part 2, then Part 3 |
| Shipping a change today | Part 4 |
| Looking at a failure | Part 5 |
| Adapting this to another client | Part 6.2 |

Throughout, every command is labelled with **where to run it**. That label matters more than the command itself.

---
---

# PART 1 — HOW IT WORKS

Read this once. Everything else makes sense afterwards.

## 1.1 The problem this solves

A Frappe app's code lives in a folder inside a running Docker container. To update it by hand you have to: SSH to the server, get a shell in the container, `git pull`, run `bench migrate`, clear the cache, and restart three services. Six steps, in the right order, in the right place. It is easy to forget one, and forgetting `migrate` or the restart means the change silently does not take effect.

CI/CD does those six steps for you, the same way every time, and tells you if any of them fails.

## 1.2 The three machines

This is the single biggest source of confusion. There are **three** different computers involved, and the shell prompt tells you which one you are on.

```
   YOUR LAPTOP                DOKPLOY SERVER              THE CONTAINER
   mohan@mohan:~$             root@vmi3305595:~#          frappe@45830ad8d5e2:~$

   git, gh, scp, ssh   ──ssh──▶  docker, systemd   ──exec──▶  bench, the app code
   browser                       /usr/local/bin               /home/frappe/frappe-bench
                                 194.146.12.226
```

| Prompt looks like | Where you are | What belongs here |
|---|---|---|
| `mohan@mohan:~$` | **Your laptop** | `git`, `gh`, `scp`, `ssh`, the browser |
| `root@vmi3305595:~#` | **Dokploy server** | `docker`, `adduser`, files in `/usr/local/bin` |
| `frappe@45830ad8d5e2:...$` | **Inside the container** | `bench` commands, `git` on the app folder |

**Moving between them:**

```bash
ssh root@194.146.12.226                       # laptop  -> server
docker exec -it <stack>-web-1 bash            # server  -> container
exit                                          # back one level
```

**Three rules that prevent most mistakes:**

1. The container is a *small* box. It has no `adduser`, no `sudo`, no `systemctl`. Do not try to create users there.
2. The container **cannot see files on your laptop**. `scp` goes laptop → server. To get a file into the container you go through the server.
3. `bench` only exists **inside the container**. `docker` only exists **on the server**.

## 1.3 What happens when you push

```
  You: git push
        │
        ▼
  ┌─────────────────────────────────────────────────────┐
  │ GITHUB ACTIONS                                      │
  │                                                     │
  │  Job 1  "check"                                     │
  │    compileall           does every file parse?      │
  │    ruff (narrow rules)  any undefined names?        │
  │         │  fails ──▶ STOP. Nothing is deployed.      │
  │         ▼ passes                                    │
  │  Job 2  "deploy"                                    │
  │    ssh deploy@194.146.12.226                        │
  │      /usr/local/bin/deploy-tnc-app.sh <app> <branch>│
  └─────────────────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────────────────┐
  │ THE SERVER runs the script (see 1.4)                │
  └─────────────────────────────────────────────────────┘
        │
        ▼
  Site is live on the new code, or the job goes red.
```

The `check` job is a gate. Broken code never reaches the server.

## 1.4 What the deploy script does, step by step

`/usr/local/bin/deploy-tnc-app.sh` is the heart of this. **One copy serves every app** on the bench — it takes the app name and branch as arguments.

| # | Step | Why it is there |
|---|---|---|
| 1 | Check the `web` container is running | Fail fast with a clear message instead of a confusing docker error |
| 2 | **Refuse if the app's working tree is dirty** | `developer_mode` writes doctype JSON into the app folder, so uncommitted changes on the server are usually someone's unsaved work. The script will not throw it away |
| 3 | Detect the git remote name | `bench get-app` names it **`upstream`**, not `origin`. Hardcoding `origin` fails |
| 4 | `git fetch`, `git checkout <branch>`, `git pull --ff-only` | `--ff-only` refuses a merge. If the server has diverged, stop rather than create a mystery merge commit |
| 5 | Print the commit range that was pulled | So the log tells you exactly what shipped |
| 6 | `bench migrate` | Applies doctype changes, patches, fixtures and customizations |
| 7 | `bench clear-cache` | Frappe caches doctype metadata aggressively |
| 8 | Restart `web`, `worker`, `scheduler` | These hold Python in memory. Without a restart, old code keeps running |
| 9 | Poll `https://<site>/api/method/ping` for up to 150s | Proves the site actually came back, not just that the commands ran |

**It exits 0 only if step 9 succeeds.** A green tick therefore means the site answered after the deploy.

### Why only those three services restart

| Service | Restarted? | Why |
|---|---|---|
| `web` | Yes | Runs `bench serve` — holds your Python in memory |
| `worker` | Yes | Runs background jobs — your hooks and scheduled methods |
| `scheduler` | Yes | Queues scheduled jobs from `hooks.py` |
| `socketio` | No | Node.js realtime server. Does not load app Python |
| `watch` | No | Rebuilds JS/CSS on change. Restarting would interrupt it |
| `db`, `redis-*` | No | Data stores. Never restart these for a code change |

## 1.5 What it deliberately does NOT do

Knowing the gaps is as important as knowing the steps. Each has a workaround in Part 4.

| Not done | Consequence | See |
|---|---|---|
| Install new Python dependencies | A push that adds a library will deploy, then crash on import | 4.6 |
| `bench build` | Relies on the `watch` container for JS/CSS | 4.7 |
| **Back up the database before migrating** | **A bad migration has no safety net** | 5.2 |
| Delete custom fields removed from JSON | Removals silently do nothing | 4.5 |
| Deploy to any other site or bench | `STACK` and `SITE` are hardcoded in the script | 6.2 |

---
---

# PART 2 — ONE-TIME SERVER SETUP

> **You probably do not need this.** It is already done on `194.146.12.226`. Do this only for a brand new server, or if `~/tncv2_deploy` is missing from your laptop.

This is done **once per server**, not per app.

## 2.1 Create the deploy user

**Run on: the Dokploy server** (as root)

```bash
adduser --disabled-password --gecos "" deploy
usermod -aG docker deploy
```

**What this does.** Creates a robot account for GitHub to log in as. `--disabled-password` means it has **no password at all** and can only be reached with an SSH key. `usermod -aG docker` lets it run `docker` commands, which is all the script needs.

**Why not just use root?** If the key ever leaks, `deploy` can restart containers. `root` can do anything to the whole server.

> **Important consequence:** because the account has no password, `ssh-copy-id deploy@...` **cannot work** — there is no password for it to authenticate with. Use 2.3.

## 2.2 Install the deploy script

**Run on: your laptop**

```bash
scp ~/tncv2-cicd/deploy-tnc-app.sh root@194.146.12.226:/usr/local/bin/deploy-tnc-app.sh
```

**Run on: the server**

```bash
chmod 755 /usr/local/bin/deploy-tnc-app.sh
bash -n /usr/local/bin/deploy-tnc-app.sh && echo "script OK"
```

`bash -n` checks the syntax without running it.

## 2.3 Create and install the SSH key

**Run on: your laptop**

```bash
ssh-keygen -t ed25519 -f ~/tncv2_deploy -N "" -C "github-actions@tnc-bench"
scp ~/tncv2_deploy.pub root@194.146.12.226:/tmp/ci.pub
```

This makes a pair: `~/tncv2_deploy` (private — goes into GitHub) and `~/tncv2_deploy.pub` (public — goes on the server).

**Run on: the server** — one line at a time; they are short so a paste cannot break across lines

```bash
install -d -m700 -o deploy -g deploy /home/deploy/.ssh
```
```bash
install -m600 -o deploy -g deploy /tmp/ci.pub /home/deploy/.ssh/authorized_keys
```
```bash
rm /tmp/ci.pub
```

`install` sets ownership and permissions in one go. SSH refuses keys with loose permissions, and gives an unhelpful error when it does.

## 2.4 Verify

**Run on: your laptop.** This must print `deploy` and three container names, **with no password prompt**:

```bash
ssh -i ~/tncv2_deploy deploy@194.146.12.226 'whoami; docker ps --format "{{.Names}}" | head -3'
```

- **Asks for a password** → the public key did not install correctly. Redo 2.3.
- **`permission denied` on docker** → the `usermod -aG docker` has not taken effect. Log the user out and back in.

---
---

# PART 3 — SETTING UP A NEW APP

## 3.0 Fill this in first

| Name | Your value | Example |
|---|---|---|
| App name (Python package) | | `tnc_v2_360ithub` |
| GitHub repo | | `360ITHUBPVTLTD/my_new_app` |
| Branch to deploy | | `360ithub_master` |
| Site name | | `tncv2.360ithub.com` |
| Dokploy stack name | | `test-demo-erpnext-w6y5gf` |

**Finding the stack name:** Dokploy → your project → the compose service → `appName`. Containers are named `<stack>-<service>-1`.

## 3.1 Is the app on the bench already?

**Run on: the server**

```bash
docker exec <stack>-web-1 ls /home/frappe/frappe-bench/apps
```

- **Listed** → skip to 3.4.
- **Not listed** → do 3.2 and 3.3.

## 3.2 Add the app to the bench

The bench is built by a bootstrap script inside the Dokploy compose file. Near the top is a list:

```
APPS=(
  "erpnext|https://github.com/frappe/erpnext.git|version-15"
  ...
  "tnc_v2_360ithub|git@github.com:360ITHUBPVTLTD/tnc_v2_360ithub.git|360ithub_master"
)
```

Format: `name|git url|branch`, separated by `|`.

1. Dokploy → your project → the compose service → **Compose** tab
2. Add one line for your app inside `APPS=( ... )`
3. Use the **SSH** URL form (`git@github.com:ORG/repo.git`), never HTTPS
4. **Save**, then **Deploy**

**Why the SSH form.** The container holds a deploy key (the `GIT_SSH_KEY_B64` environment variable), registered on the GitHub account **`360ithubdev`**. SSH is what lets the container pull *and push*. If your repo is in the `360ITHUBPVTLTD` org and `360ithubdev` can read it, this works with no extra setup.

> **If the clone fails with `Permission denied (publickey)`:** grant the `360ithubdev` account read access to the repo on GitHub.

## 3.3 Install the app on the site — DO NOT SKIP

**This is the step everyone misses, and it fails silently.**

The bootstrap script *downloads* new apps but does **not** install them on the site. The install loop is guarded by:

```bash
if [ ! -f "$SENTINEL" ]; then      # sites/.bootstrap-complete
```

That sentinel file already exists on any working bench, so the guard is false and the whole install loop is skipped. Your app ends up in `apps/` but missing from the site. Nothing errors. Nothing works.

**Run on: the server**

```bash
docker exec -it <stack>-web-1 bash
```

**Then inside the container:**

```bash
cd /home/frappe/frappe-bench
bench --site <site> install-app <app_name>
bench --site <site> migrate
bench --site <site> list-apps
exit
```

Your app must appear in the `list-apps` output. If it does not, stop here — the pipeline cannot help an app that is not installed.

## 3.4 Add the workflow file

### Create it in the browser

Use this URL, replacing `ORG/REPO` and `BRANCH`:

```
https://github.com/ORG/REPO/new/BRANCH?filename=.github/workflows/deploy.yml
```

The `?filename=` part pre-fills the path so it cannot go wrong.

> ### The classic mistake
> Typing the workflow's **name** (`Deploy to tncv2 bench`) into the **filename** box. That creates a junk file at the repo root and GitHub silently ignores it — no error, no run, nothing.
>
> - The **filename** must be exactly `.github/workflows/deploy.yml`
> - The **name** goes *inside* the file, on the first line
>
> GitHub only runs workflows found in `.github/workflows/`.

### Paste this in

A ready-to-edit copy is at `~/tncv2-cicd/deploy.yml.template`. Change the four marked lines.

```yaml
name: Deploy to tncv2 bench

on:
  push:
    branches: [360ithub_master]          # <-- 1. your branch
    paths-ignore:
      - '**.md'
      - 'license.txt'
  workflow_dispatch:

# One bench, one deploy at a time. Never cancel a run mid-migrate.
concurrency:
  group: deploy-tncv2-my_new_app         # <-- 2. unique per app
  cancel-in-progress: false

jobs:
  check:
    name: Syntax and undefined names
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Compile every module
        run: python -m compileall -q my_new_app        # <-- 3. app name
      - name: Ruff (breakage-only rules)
        run: |
          pip install --quiet ruff==0.8.1
          ruff check --select=E9,F821,F632,F702 --no-cache .

  deploy:
    name: Deploy to the bench
    needs: check
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1.2.0
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          command_timeout: 20m
          script: /usr/local/bin/deploy-tnc-app.sh my_new_app 360ithub_master
          #                                        ^ 4. app and branch
```

Commit it to a **new branch**, not your main branch. You want to smoke test before it goes live.

### Two design choices worth understanding

**`workflow_dispatch`** adds a **Run workflow** button in the Actions tab, so you can deploy on demand without pushing anything.

**`concurrency`** means one deploy at a time per app. `cancel-in-progress: false` is deliberate: cancelling a run halfway through `bench migrate` could leave the database half-migrated. Better to queue.

### Why the lint step is so narrow

`ruff check .` with the app's own `pyproject.toml` reports hundreds of style findings on a typical existing app — `tnc_v2_360ithub` had **375**. Gate deploys on that and your pipeline is red forever, and people learn to ignore it.

`E9,F821,F632,F702` is the subset meaning *"this will actually crash"*: syntax errors, undefined names, bad comparisons. It passes on a healthy app today. Widen it later as the style backlog is cleaned up.

## 3.5 Add the three GitHub secrets

These tell GitHub how to log into the server. **Secrets are per-repository**, so every app repo needs its own copy even though the values are identical.

Browser: **your repo → Settings → Secrets and variables → Actions → New repository secret.** Three of them:

| Name | Value |
|---|---|
| `DEPLOY_HOST` | `194.146.12.226` |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | the entire contents of `~/tncv2_deploy` |

**Run on: your laptop** to get the key:

```bash
cat ~/tncv2_deploy | xclip -selection clipboard     # copy to clipboard
cat ~/tncv2_deploy                                  # or print and select
```

**Copy all of it**, including the `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----` lines. A partial paste is the most common cause of a failed first deploy.

> Use `~/tncv2_deploy`, **not** `~/tncv2_deploy.pub`. GitHub needs the *private* key. The public half is already on the server.

GitHub will not show you a secret again after saving — only overwrite it. If unsure, click the secret and **Update** with a fresh paste.

## 3.6 Smoke test — do not skip

Everything the pipeline does, this one command does too. Debugging from your own terminal is far easier than from a red Actions log.

**Run on: your laptop**

```bash
ssh -i ~/tncv2_deploy deploy@194.146.12.226 \
  '/usr/local/bin/deploy-tnc-app.sh my_new_app 360ithub_master'
```

Success ends with:

```
==> deployed my_new_app@360ithub_master - site is up
```

> **The site restarts during this**, so expect 30–60 seconds of downtime. Run it at a quiet time.

If it fails, fix it here using Part 5 **before** touching GitHub.

## 3.7 Merge and turn it on

Open a pull request from your branch, review, merge. Merging pushes to your main branch, which fires the workflow immediately. Because 3.5 and 3.6 are already done, that first run should go green on its own.

## 3.8 Verify it really worked

A green tick means the script exited 0. Confirm the code actually landed.

**1. Watch the run:** repo → **Actions**. Both jobs green.

**2. Compare server against GitHub. Run on: your laptop**

```bash
ssh -i ~/tncv2_deploy deploy@194.146.12.226 \
  'docker exec <stack>-web-1 git -C /home/frappe/frappe-bench/apps/my_new_app log -1 --oneline'
```

That commit must match the top of your branch on GitHub.

**3. The real test.** Make a trivial change — add a comment — commit, push to your main branch, and watch it deploy with you doing nothing. That is CI/CD working.

---
---

# PART 4 — DAY TO DAY: SHIPPING A CHANGE

## 4.1 The normal workflow

```
  work locally  ──▶  commit  ──▶  push branch  ──▶  open PR
                                                       │
                                    review ◀───────────┘
                                       │
                                     merge
                                       │
                                       ▼
                            pipeline deploys automatically
```

**Never edit code directly on the server.** Two reasons: your change would be lost the next time someone deploys, and the script's dirty-tree guard will block everyone else's deploys until someone cleans it up.

## 4.2 Ordinary Python change

Nothing special. Commit, push, merge. Done.

## 4.3 New or changed doctype

Nothing special. `bench migrate` syncs doctype JSON automatically. Commit the generated `<doctype>.json` along with your Python.

## 4.4 Adding a Customize Form field

Works as you would expect:

1. Add the field on your local bench via **Customize Form**
2. **Customize Form → Export Customizations**, choosing your app and module
3. Commit the changed `<app>/<module>/custom/<doctype>.json`
4. Push, merge — the field appears on the server

## 4.5 Removing a Customize Form field — THE BIG GOTCHA

> **By default, removing a field does nothing.** The deploy runs green, `bench migrate` runs, and the field is still there on the server. Forever.

**Why.** `bench migrate` calls frappe's `sync_customizations`, whose Custom Field branch only **inserts** what is missing and **updates** what is already there. It never **deletes** a field you removed from the JSON. (`Custom DocPerm`, a few lines below in the same frappe function, *is* deleted and reinserted — so the asymmetry is deliberate.)

It is worse than it sounds: the whole branch is wrapped in `if data["custom_fields"]:`, so removing the **last** field from a doctype is a complete no-op.

| Action | Works via JSON alone? |
|---|---|
| Add a field | Yes |
| Change a label, options, or position | Yes |
| **Remove a field** | **No** |
| **Rename a fieldname** | **No** — creates a second field, old one stays |

**The fix: install the reconciler.** Copy `customizations.py` from `tnc_v2_360ithub` into your app, set the `APP` constant to your app name, and register it **last** in `after_migrate`:

```python
after_migrate = [
    # ... your existing hooks ...
    "my_new_app.customizations.reconcile_custom_fields",   # keep LAST
]
```

It must be last because it reads the `is_system_generated` flag, and other hooks may change that flag.

It **reports only** until you arm the site:

```bash
bench --site <site> set-config -g reconcile_custom_fields 1 --parse
```

The first deploy after installing it prints every leftover field it found and deletes nothing. Read that list — it is your accumulated backlog — then arm it.

> ### What you are agreeing to when you arm it
> The repo becomes the single source of truth. **Any custom field someone created directly on the live site through Customize Form and never exported will be deleted on the next deploy.**
>
> Tell your team: customizations are changed locally, exported, and merged. Never edited on the live site. If a site must allow live editing, leave it unarmed.

**Safety limits built in:**

| Limit | Behaviour |
|---|---|
| Report-only until armed | Nothing deleted until you opt in per site |
| Ceiling of 5 deletions per doctype | More than that usually means the JSON was exported from a bench missing an app, so it under-declares reality. It refuses and prints |
| `reconcile_custom_fields_max_deletions` | Raise the ceiling per site when clearing a big backlog |
| `dry_run=True` | Preview by hand at any time |

**Property Setters are not covered.** They have the same root cause but carry no `is_system_generated` flag, so yours cannot be told from another app's. Removing a property setter still needs an explicit patch.

## 4.6 Adding a new Python dependency — KNOWN GAP

> **The deploy script does not install dependencies.** If your push adds a library to `pyproject.toml` or `requirements.txt`, the deploy will succeed and then the app will crash on import.

**After merging such a change, run this once. On: the server**

```bash
docker exec -it <stack>-web-1 bash
```

**Inside the container:**

```bash
cd /home/frappe/frappe-bench
./env/bin/pip install -e apps/my_new_app
exit
```

**Back on the server:**

```bash
docker restart <stack>-web-1 <stack>-worker-1 <stack>-scheduler-1
```

Note `./env/bin/pip`, not plain `pip` — the bench has its own virtualenv.

## 4.7 JS / CSS change

Usually automatic. The `watch` container runs `bench watch` and rebuilds assets when files change.

If your change does not appear:

1. **Hard-refresh the browser** (Ctrl+Shift+R). Frappe caches assets aggressively.
2. Build by hand. **Inside the container:**
   ```bash
   cd /home/frappe/frappe-bench
   bench build --app my_new_app
   ```

`bench watch` is not always reliable at noticing files that changed via a `git checkout`, as opposed to being edited in place.

## 4.8 Data migration (a patch)

To change existing data — backfill a field, delete an old record, fix bad values — write a patch. Patches run once per site and are recorded in the `Patch Log`, so they are safe to leave in place forever.

**1. Create `my_new_app/patches/v1_0/fix_something.py`:**

```python
import frappe

def execute():
	# Runs once per site, then never again.
	frappe.db.set_value("Some Doctype", "some-name", "field", "value")
```

**2. Register it in `my_new_app/patches.txt`** under `[post_model_sync]`:

```
my_new_app.patches.v1_0.fix_something
```

**3. Commit, push, merge.** `bench migrate` runs it.

**Which section?** `[pre_model_sync]` runs *before* doctypes are synced — use it when you need the old schema. `[post_model_sync]` runs after — use it for almost everything.

## 4.9 Two people merging at once

The `concurrency` group means one deploy at a time per app. GitHub queues **one** pending run; if a third arrives, the middle one is cancelled.

That sounds alarming but is harmless: **each deploy pulls the current branch head**, not the specific commit that triggered it. So a skipped middle run still ends with the server on the latest code. You may just not see a separate green tick for every merge.

## 4.10 Deploying without pushing

Two ways to deploy on demand:

**From GitHub:** repo → **Actions** → your workflow → **Run workflow**.

**From your laptop:**
```bash
ssh -i ~/tncv2_deploy deploy@194.146.12.226 \
  '/usr/local/bin/deploy-tnc-app.sh my_new_app 360ithub_master'
```

The same command works for any app on the bench — swap the name and branch.

---
---

# PART 5 — WHEN THINGS GO WRONG

## 5.1 How to tell whether a deploy really worked

**Never judge by how long the log is.** `bench migrate` prints thousands of progress-bar lines which can flood and truncate the log, making a perfectly healthy deploy look like it hung. Check facts instead.

**Did the containers restart? Run on: the server**

```bash
docker ps --format "{{.Names}}\t{{.Status}}" | grep <stack>
```

`web`, `worker` and `scheduler` showing "Up a minute" means the script **reached step 8**, which it only does if `migrate` succeeded. `db`, `redis-*` and `socketio` showing days of uptime is correct — they are not restarted.

**Is the app at the commit you expect? Run on: the server**

```bash
docker exec <stack>-web-1 git -C /home/frappe/frappe-bench/apps/my_new_app log -1 --oneline
```

Compare with the top of your branch on GitHub. If they match, the code landed.

## 5.2 Rolling back a bad deploy

> ### Read this before you need it
> **There is no automated backup on this bench.** No compose backup, no volume backup, no scheduled dump. A bad migration that corrupts or drops data has **no safety net**.
>
> `bench migrate` is also **not reversible**. Rolling code back does not undo a schema change or a patch that already modified data.
>
> **Setting up a daily database backup in Dokploy should be treated as a prerequisite for running automated migrations, not a nice-to-have.**

### Option A — revert on GitHub (preferred)

```bash
# on your laptop, in your local clone
git revert <bad-commit-sha>
git push
```

The pipeline deploys the revert like any other change. Permanent, auditable, and every other bench gets the fix too.

### Option B — emergency rollback on the server

Faster, but **temporary** — the next deploy will pull forward again.

**On: the server**

```bash
docker exec -it <stack>-web-1 bash
```

**Inside the container:**

```bash
cd /home/frappe/frappe-bench/apps/my_new_app
git log --oneline -10                 # find the last good commit
git checkout <good-sha>
cd /home/frappe/frappe-bench
bench --site <site> migrate
bench --site <site> clear-cache
exit
```

**On: the server**

```bash
docker restart <stack>-web-1 <stack>-worker-1 <stack>-scheduler-1
```

Then do Option A properly, so the fix is permanent.

> **Remember:** neither option undoes a data change a patch already made, or a column a migration dropped. Only a database restore does that.

## 5.3 Error reference

Every error below was hit for real while setting this up the first time.

### `fatal: 'origin' does not appear to be a git repository`

`bench get-app` names the git remote **`upstream`**, not `origin`. The current script detects this. Your server copy is out of date:

```bash
scp ~/tncv2-cicd/deploy-tnc-app.sh root@194.146.12.226:/usr/local/bin/deploy-tnc-app.sh
```

### `FATAL: <app> has uncommitted changes on the server`

Working as designed — the guard from step 2. Somebody edited something on the server, probably doctypes through the UI.

**On: the server**

```bash
docker exec -it <stack>-web-1 bash
cd /home/frappe/frappe-bench/apps/my_new_app
git status
```

Commit and push what is worth keeping; `git checkout -- .` discards the rest. Then re-run the deploy.

### `refusing to allow an OAuth App to create or update workflow ... without 'workflow' scope`

Your `gh` CLI token cannot push files under `.github/workflows/`.

```bash
gh auth refresh -h github.com -s workflow
```

The browser must be signed in as the **same account** `gh` is logged in as — check with `gh auth status`. A mismatch gives `received credentials for <other account>`. Use a private browser window to control which account you are signed in as.

Simplest alternative: create the file in the browser (3.4). No scope restriction there.

### The log stops at `Updating DocTypes for frappe ... 100%`

`bench migrate` prints a progress-bar line per percent per app — thousands of lines that flood the log and cause everything after them to be dropped. The deploy almost certainly succeeded.

The current script captures and filters migrate output. If you still see this, update the server copy (first entry above). To confirm the deploy worked meanwhile, use 5.1.

### `ssh-copy-id` asks for a password that does not exist

The `deploy` user was created with `--disabled-password` on purpose. Use 2.3, which installs the key through your existing root access.

### The site never comes back; the job times out after 150s

**On: the server**

```bash
docker logs --tail 100 <stack>-web-1
```

The bootstrap script runs on every container start. It is guarded by a sentinel file, so a restart is normally a no-op that goes straight to `bench serve`. If it is stuck waiting for `db` or `redis`, those containers are the problem, not your code.

### The app crashes with `ModuleNotFoundError` right after a deploy

A new Python dependency was added but not installed. See 4.6.

### `bench migrate` fails on a fresh site

On a site where the ERPNext setup wizard has not been completed, hooks that create records under `All Customer Groups` or `All Item Groups` raise a link error. Because `after_migrate` propagates, the whole migrate exits 1.

Gate any such hook:

```python
if not frappe.db.get_single_value("System Settings", "setup_complete"):
    return
```

### A field I removed from `custom/*.json` is still on the site

Expected. See 4.5.

### The workflow did not run at all

Check, in order:

1. Is the file at exactly `.github/workflows/deploy.yml`? (3.4)
2. Does the `branches:` list match the branch you pushed to?
3. Did your commit only touch files in `paths-ignore` (`**.md`, `license.txt`)?
4. Is the workflow on your **default branch**? A workflow on a feature branch does not run on pushes to other branches.

---
---

# PART 6 — REFERENCE

## 6.1 Files and where they live

| File | Location | What it is |
|---|---|---|
| `deploy-tnc-app.sh` | `/usr/local/bin/` **on the server** | Does the work. Generic — takes `<app> <branch>`. One copy for all apps |
| `deploy-tnc-app.sh` | `deploy/` in the app repo | Reviewable source of truth. **Editing this does not change the server** |
| `deploy.yml` | `.github/workflows/` in each app repo | Tells GitHub to run the script on push. One per app |
| `deploy.yml.template` | `~/tncv2-cicd/` | Fill-in-the-blanks copy for a new app |
| `~/tncv2_deploy` | your laptop | Private SSH key → `DEPLOY_SSH_KEY` |
| `~/tncv2_deploy.pub` | laptop + `/home/deploy/.ssh/authorized_keys` | Public half |
| `customizations.py` | in the app repo | Optional. Makes custom field removals apply (4.5) |

### The one thing that surprises everyone

The script that runs on every deploy lives at `/usr/local/bin/` **on the server**. The copy in git is documentation. **Merging a change to the repo copy does nothing** until you run:

```bash
scp ~/tncv2-cicd/deploy-tnc-app.sh root@194.146.12.226:/usr/local/bin/deploy-tnc-app.sh
```

## 6.2 Adapting this to another client bench

360ITHub runs many client benches. To reuse this setup, note that **the script hardcodes two values**:

```bash
STACK=test-demo-erpnext-w6y5gf
SITE=tncv2.360ithub.com
```

You have two options:

**Option A — one script per bench.** Copy it as `/usr/local/bin/deploy-<client>-app.sh` with that client's `STACK` and `SITE`. Simple, and safe because a mistake cannot hit the wrong bench.

**Option B — parameterise it.** Take `STACK` and `SITE` as a third and fourth argument, or from environment variables. Fewer copies, but one typo in a workflow file could deploy to the wrong client.

**Option A is recommended** while the number of benches is small. Getting the wrong client's site restarted is a bad failure.

Everything else carries over unchanged: same `deploy` user pattern, same key handling, same workflow shape.

## 6.3 Security notes

| Item | Note |
|---|---|
| `DEPLOY_SSH_KEY` | Grants SSH access to the server as `deploy`. Anyone with repo admin can read your secrets list, though not the values |
| `deploy` user | In the `docker` group, which is effectively root on the host. Keep the key safe |
| Rotating the key | Generate a new pair (2.3), replace `authorized_keys` on the server, update `DEPLOY_SSH_KEY` in **every** app repo |
| The container's deploy key | A separate key (`GIT_SSH_KEY_B64`), on the `360ithubdev` account, used for pulling from GitHub. Different direction, different key |
| If someone leaves the team | Rotate both keys |

## 6.4 Things that look like they would work, but do not

### Dokploy's Deploy button does not ship app code

It redeploys the *compose stack*, which cannot do this job:

- the bootstrap **skips any app whose folder already exists**, so it never pulls
- `docker compose up -d` with an unchanged compose file **does not recreate containers at all**, so the bootstrap does not even re-run

App code lives on the `bench-data` volume, one layer below what Dokploy manages. Dokploy's Deploy button is for changes to the **compose file itself** — like adding an app in 3.2.

### Dokploy's auto-deploy webhook does not help either

Same reason. The compose service has `autoDeploy: true`, but it triggers a compose redeploy, not an app pull.

### Editing code in the container does not survive

The next deploy's `git pull --ff-only` either overwrites it or, more likely, the dirty-tree guard blocks every deploy until someone cleans it up.

### A green tick alone does not prove the code is live

It proves the script exited 0. Confirm with 5.1 when it matters.

## 6.5 One-page summary

```
ONE TIME PER SERVER  (done for 194.146.12.226)
  adduser deploy + add to docker group             [server]
  scp deploy-tnc-app.sh to /usr/local/bin          [laptop -> server]
  ssh-keygen; install pubkey via root              [laptop -> server]
  verify passwordless ssh as deploy                [laptop]

PER NEW APP
  1. is the app on the bench?                      [server]
       no -> add to compose APPS, Deploy           [browser]
          -> bench install-app + migrate BY HAND   [container]   <-- easy to miss
  2. create .github/workflows/deploy.yml           [browser]
       change: branch, concurrency group, app x2
  3. add DEPLOY_HOST / DEPLOY_USER / DEPLOY_SSH_KEY  [browser]
  4. smoke test the script over ssh                [laptop]      <-- do not skip
  5. merge the PR                                  [browser]
  6. verify server commit == GitHub commit         [laptop]
  7. shipping Customize Form fields? add the reconciler (4.5)

EVERY DAY
  work locally -> commit -> push -> PR -> merge -> it deploys itself

REMEMBER
  removing a custom field needs the reconciler        (4.5)
  a new python dependency needs a manual pip install  (4.6)
  there is NO database backup on this bench           (5.2)
  editing the repo copy of the script changes nothing until you scp it  (6.1)
```
