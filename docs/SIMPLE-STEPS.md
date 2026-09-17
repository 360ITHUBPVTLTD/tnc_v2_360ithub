# CI/CD Setup — Simple Steps

## You only create ONE file

For a new app you create **one file**, in the app's GitHub repo:

```
.github/workflows/deploy.yml
```

Everything else already exists on the server and is shared by all apps.

---

## Fill this in first

| | Your value | Example |
|---|---|---|
| App name | | `my_new_app` |
| GitHub repo | | `360ITHUBPVTLTD/my_new_app` |
| Branch | | `360ithub_master` |
| Site | | `tncv2.360ithub.com` |
| Stack | | `test-demo-erpnext-w6y5gf` |

---

## Where to run each command

Look at your shell prompt:

| Prompt | You are on |
|---|---|
| `mohan@mohan:~$` | **Laptop** |
| `root@vmi3305595:~#` | **Server** |
| `frappe@45830...:~$` | **Container** |

To move: `ssh root@194.146.12.226` (laptop → server), then
`docker exec -it <stack>-web-1 bash` (server → container), `exit` to go back.

---

## STEP 1 — Is the app on the bench?

**On: SERVER**

```bash
docker exec <stack>-web-1 ls /home/frappe/frappe-bench/apps
```

- App is listed → **go to Step 3**
- Not listed → **do Step 2**

---

## STEP 2 — Put the app on the bench

### 2a. In Dokploy (browser)

Open your compose service → **Compose** tab. Find `APPS=(` and add one line:

```
"my_new_app|git@github.com:360ITHUBPVTLTD/my_new_app.git|360ithub_master"
```

Format is `name|git url|branch`. Use the `git@github.com:` form, not `https://`.

Click **Save**, then **Deploy**. Wait for it to finish.

### 2b. Install it on the site

**On: SERVER**

```bash
docker exec -it <stack>-web-1 bash
```

**On: CONTAINER**

```bash
cd /home/frappe/frappe-bench
bench --site <site> install-app my_new_app
bench --site <site> migrate
bench --site <site> list-apps
exit
```

Your app must appear in the `list-apps` output.

> **Why this step exists:** the Dokploy deploy downloads the app but does **not**
> install it. It fails silently. Do not skip it.

---

## STEP 3 — Create the workflow file

**On: BROWSER**

Open this link (change `ORG/REPO` and `BRANCH`):

```
https://github.com/ORG/REPO/new/BRANCH?filename=.github/workflows/deploy.yml
```

The filename box is already filled in. **Do not change it.**

Paste the contents of `deploy.yml.template`, then change the 4 marked lines:

```yaml
name: Deploy to tncv2 bench

on:
  push:
    branches: [360ithub_master]          # 1. your branch
    paths-ignore: ['**.md', 'license.txt']
  workflow_dispatch:

concurrency:
  group: deploy-my_new_app               # 2. your app name
  cancel-in-progress: false

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python -m compileall -q my_new_app        # 3. your app name
      - run: |
          pip install --quiet ruff==0.8.1
          ruff check --select=E9,F821,F632,F702 --no-cache .

  deploy:
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
          #                                        4. app and branch
```

At the bottom choose **Create a new branch**, then **Commit**.

> **Most common mistake:** typing the name `Deploy to tncv2 bench` into the
> *filename* box. The filename must be `.github/workflows/deploy.yml`.

---

## STEP 4 — Add 3 secrets

**On: BROWSER** — your repo → **Settings → Secrets and variables → Actions →
New repository secret**. Add three:

| Name | Value |
|---|---|
| `DEPLOY_HOST` | `194.146.12.226` |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | whole contents of `~/tncv2_deploy` |

**On: LAPTOP** to get the key:

```bash
cat ~/tncv2_deploy
```

Copy **everything**, including the `-----BEGIN` and `-----END` lines.

> Use `~/tncv2_deploy`, NOT `~/tncv2_deploy.pub`.

---

## STEP 5 — Test before turning it on

**On: LAPTOP**

```bash
ssh -i ~/tncv2_deploy deploy@194.146.12.226 \
  '/usr/local/bin/deploy-tnc-app.sh my_new_app 360ithub_master'
```

Must end with:

```
==> deployed my_new_app@360ithub_master - site is up
```

> The site restarts — about 30–60 seconds down. Do not skip this step. It is
> much easier to fix a problem here than in a red Actions log.

---

## STEP 6 — Merge

**On: BROWSER** — open a pull request from your branch and merge it.

The workflow runs automatically. Watch it: repo → **Actions**.

---

## STEP 7 — Check it really worked

**On: LAPTOP**

```bash
ssh -i ~/tncv2_deploy deploy@194.146.12.226 \
  'docker exec <stack>-web-1 git -C /home/frappe/frappe-bench/apps/my_new_app log -1 --oneline'
```

That commit must match the latest commit on GitHub.

**Done.** From now on, every push to your branch deploys automatically.

---
---

# After setup: what to remember

## Normal work

Work locally → commit → push → open PR → merge → it deploys itself.

**Never edit code on the server.** It gets lost, and it blocks everyone else's
deploys.

## 3 things that need manual work

| You did this | Extra step needed |
|---|---|
| Added a Python library to `pyproject.toml` | On CONTAINER: `cd /home/frappe/frappe-bench && ./env/bin/pip install -e apps/my_new_app` then restart the containers |
| **Removed** a Customize Form field | Does nothing by itself. Needs the reconciler — ask Claude |
| Changed `deploy-tnc-app.sh` in the repo | On LAPTOP: `scp ~/tncv2-cicd/deploy-tnc-app.sh root@194.146.12.226:/usr/local/bin/deploy-tnc-app.sh` |

## If something fails

| Error | Fix |
|---|---|
| `'origin' does not appear to be a git repository` | Server has an old script. `scp` the new one (row 3 above) |
| `has uncommitted changes on the server` | Someone edited on the server. On CONTAINER: `cd /home/frappe/frappe-bench/apps/my_new_app && git status`, then commit or `git checkout -- .` |
| Log stops at `Updating DocTypes ... 100%` | Not a failure. Log got flooded. Use Step 7 to check |
| Workflow did not run at all | Check filename is exactly `.github/workflows/deploy.yml`, and the branch name matches |
| `ModuleNotFoundError` after deploy | New Python library not installed. See table above |

## How to roll back

Best way — **on LAPTOP**, in your local clone:

```bash
git revert <bad-commit>
git push
```

The pipeline deploys the revert automatically.

> ⚠️ **There is no database backup on this bench.** `bench migrate` cannot be
> undone. If a migration damages data, there is nothing to restore from. Setting
> up a daily backup in Dokploy should be done before relying on this.
