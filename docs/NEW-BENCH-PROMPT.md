# Prompt: create a new client bench

Use this when you want a **brand new Dokploy project** — a new company, its own
site, its own apps. Once the bench is live, use `CLAUDE-PROMPT.md` to put CI/CD
on each custom app.

Edit the input block, paste the whole thing into Claude Code.

---

```
Create a new Frappe/ERPNext v15 bench on our Dokploy server for a new client,
as its own Dokploy project, then set up CI/CD for its custom apps.

=== THE INPUT I AM GIVING YOU ===

Client / company:         <<Acme Coaching>>
Site domain:              <<erp.acme.com>>
Frappe / ERPNext branch:  <<version-15>>
Standard apps:            <<erpnext, hrms, india_compliance>>
Custom apps, one per line as  name|git url|branch :
  <<erp_acme_custom|git@github.com:360ITHUBPVTLTD/erp_acme_custom.git|360ithub_master>>
  <<clarity_360ithub|git@github.com:360ITHUBPVTLTD/clarity_360ithub.git|tnc_v2>>

Dokploy server:  194.146.12.226

=== COPY THE WORKING ONE. DO NOT INVENT A COMPOSE FILE. ===

There is a working reference bench already running:
  project   "TEST DEMO"   projectId JC_puT3hZAItVL0Sxg73Q
  compose   "tncv2-bench" composeId XseUn4r7G6aZ50wjsYH_I

Read it with the dokploy MCP (compose-getConvertedCompose) and adapt it. Every
trap listed at the bottom of this prompt is already solved in that file. Writing
a fresh compose from the public Frappe docker docs will reintroduce all of them.

Change only:
  - the APPS=( ) list, from my input above
  - SITE_NAME
  - the Traefik host rules
  - passwords
Keep everything else byte for byte unless you can tell me why it must change.

=== STEP 1: CHECK BEFORE YOU BUILD ANYTHING ===

a) Confirm the DNS A record for the domain already points at 194.146.12.226.
   Let's Encrypt validates over HTTP, so if DNS is not live first the
   certificate fails and the site is stuck on plain HTTP. Tell me to fix DNS and
   WAIT if it is not resolving yet.

b) List existing Dokploy projects (project-all) and confirm the name and site do
   not collide with one already there.

c) For each private custom app repo, confirm the GitHub account `360ithubdev`
   can read it - that is the account the in-container deploy key belongs to. If
   not, tell me to grant access before we start, or the clone fails mid-build.

d) Check whether any custom app declares `required_apps` in its hooks.py. Frappe
   hard-fails the install if one is missing, and it is easy to leave out of the
   APPS list. tnc_v2_360ithub requires erpnext, hrms AND india_compliance.

Show me what you found and WAIT for my OK before creating anything.

=== WHO DOES WHAT ===

YOU do, through the dokploy MCP - I am not creating anything by hand:
  project-create, compose-create, compose-update (the compose file),
  compose-saveEnvironment (the env vars), domain-create, compose-deploy.

I do, because you cannot:
  - point the DNS A record at the server (before you deploy anything)
  - grant 360ithubdev read access to any private repo that lacks it
  - complete the ERPNext setup wizard at the end
  - copy GIT_SSH_KEY_B64 across from an existing bench, if you need me to:
    Dokploy -> the tncv2-bench compose -> Environment -> copy that value.
    The MCP redacts it, so you cannot read it yourself.

Ask me for anything on my list at the moment you need it, not all at the start.

=== STEP 2: CREATE THE PROJECT AND COMPOSE ===

Create the Dokploy project, then a compose service of type "raw" with the
adapted compose file. Order the APPS list so dependencies come before the apps
that need them: erpnext, hrms, india_compliance, then our custom apps.

Set these env vars yourself with compose-saveEnvironment:
  SITE_NAME, DB_ROOT_PASSWORD, ADMIN_PASSWORD,
  GIT_SSH_KEY_B64, GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL

Generate DB_ROOT_PASSWORD and ADMIN_PASSWORD yourself - long and random. Do NOT
print them in the chat. Tell me instead that I can read them in Dokploy under
the compose service's Environment tab, and that I will need ADMIN_PASSWORD to
log in as Administrator at the end.

=== STEP 3: DOMAINS ===

Two domains on the compose service:
  <site>/            -> service web       port 8000   https, letsencrypt
  <site>/socket.io   -> service socketio  port 9000   https, letsencrypt

CRITICAL: Dokploy has silently set the web domain's port to 8080 after creation
before. Traefik then emits loadbalancer.server.port 8080 while bench serves on
8000, which is a permanent 502 that looks exactly like "still building". After
creating the domains, read the CONTAINER's traefik labels and confirm 8000 -
do not trust the Domains tab.

=== STEP 4: DEPLOY AND WATCH IT ===

The first build takes several minutes (bench init, get-app for every app, bench
build, new-site, install-app for every app, migrate). Tell me how to follow the
logs and what the normal milestones look like, so I can tell "slow" from "stuck".

=== STEP 5: VERIFY BEFORE HANDING IT OVER ===

Check and report each of these, do not assume:
  - HTTP 200 on https://<site> with a valid Let's Encrypt certificate
  - window.dev_server is 0   (if it is 1, realtime will break behind Traefik)
  - hashed asset files return 200
  - /socket.io/?EIO=4&transport=polling returns 200
  - http redirects to https
  - every app from my list appears in sites/apps.txt
  - all containers running: init-perms completed, db healthy, web, socketio,
    scheduler, worker, watch up

=== STEP 6: HAND OVER ===

Tell me to:
  - log in as Administrator and complete the ERPNext setup wizard
  - then re-run `bench --site <site> migrate`

Explain why: several after_migrate hooks create records under ERPNext's root
trees ("All Customer Groups", "All Item Groups"), which the setup wizard creates.
On a fresh site those hooks fail and migrate exits 1 until the wizard is done.

Also tell me, once, that this bench has NO database backup until I create one in
Dokploy, and that bench migrate cannot be undone.

=== STEP 7: CI/CD ===

For each custom app in my list, set up the deploy pipeline. The reusable prompt
for this is docs/CLAUDE-PROMPT.md in the tnc_v2_360ithub repo - follow it rather
than improvising. In short:
  - the shared script is /usr/local/bin/deploy-tnc-app.sh <app> <branch> <stack> <site>
  - the workflow needs DEPLOY_HOST / DEPLOY_USER / DEPLOY_SSH_KEY per repo
  - if an app is on several benches, the workflow uses a matrix with
    fail-fast: false
  - smoke test one target by hand before turning the workflow on

=== THINGS YOU MUST KNOW. These are all real failures we have already had. ===

BENCH IMAGE
- Pin the versions. In frappe/bench:v5.31.0 the defaults are python 3.14 and
  node 24, both too new for v15. Set PYENV_VERSION=3.12.14 and put
  /home/frappe/.nvm/versions/node/v22.23.2/bin FIRST on PATH.
- Never use `bash -l`. A login shell re-sources .bashrc and puts node 24 back on
  PATH, undoing the pin. Use `bash -c` with an explicit PATH.

PROCESSES
- Never run `bench start` behind a reverse proxy. It sets DEV_SERVER=true, which
  makes window.dev_server=1, and frappe's socketio client then dials
  https://<site>:9000 directly instead of the origin - realtime breaks behind
  Traefik. Run each process as its own service: bench serve, bench socketio,
  bench schedule, bench worker, bench watch.
- developer_mode in site config is unrelated to DEV_SERVER and is safe to enable.
- Do NOT set webserver_port in the config. frappe's get_url() appends it to every
  generated link, putting ":8000" into emails, PDFs and redirects. `bench serve`
  takes its port from the --port flag.
- `bench serve` serves /assets and /files itself, so a dev bench needs no nginx
  container.

VOLUMES AND INIT
- `bench init` refuses a non-empty path and a mounted volume already exists, so
  pass --ignore-exist.
- Docker creates named volumes root-owned while the image runs as frappe (uid
  1000). Chown them first in an init service running as user "0:0".

BOOTSTRAP SCRIPT
- Gate "have I finished" work on a sentinel file written at the very END, never
  on flags describing what this run happened to do. After an interruption the
  apps dir and site dir already exist, so such flags are 0 and the remaining work
  is silently skipped.
- `bench migrate` exits 1 if any after_migrate hook raises, even though the
  schema changes already applied. Under `set -e` that kills the container. Guard
  it and carry on, so the site still serves.
- `bench install-app` is idempotent only for a FULLY installed app. An install
  interrupted partway leaves rows behind (e.g. Module Def "HR" from hrms) without
  the app being recorded, and the retry dies on a duplicate key. Always wrap it:
  plain install, then retry with --force on failure.

GIT
- `bench get-app` names the remote `upstream`, not `origin`, and clones shallow
  and single-branch. To get full history in a dev bench:
  git remote set-branches upstream '*' && git fetch --unshallow upstream
- Use git@github.com: URLs for our own repos, not https, so the container can
  push as well as pull.

DOKPLOY
- Dokploy's Deploy button and auto-deploy webhook redeploy the COMPOSE STACK.
  They cannot deploy app code: the bootstrap skips any app whose folder already
  exists, and an unchanged compose file does not recreate containers at all.
  Use the Deploy button only for compose file changes.
- Adding an app to the APPS list and redeploying FETCHES it but does NOT install
  it on the site, because the install loop is behind the sentinel check. Always
  follow up with `bench --site <site> install-app <app>` by hand.

=== HOW TO WORK WITH ME ===

- Show me your findings and wait for my OK before creating anything in Dokploy.
- Short numbered steps. One command per step. Always say which machine to run it
  on: my laptop, the Dokploy server (194.146.12.226), or the container.
- Tell me what I should see when a step works.
- Never tell me something is "on your clipboard". xclip does not survive the
  command that set it. Print file contents in full in the chat AND save them to a
  file, and give me the `cat` command for it.
- Never print a password or a private key. Give me the command that generates it.
- When you say something works, prove it - status codes, container states, the
  contents of apps.txt. Not "it should be fine".
```
