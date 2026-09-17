# Prompt: create a new client bench

Use this for a **brand new Dokploy project** — new company, its own site, its own
apps. Works on **any** Dokploy server: the compose file is included in full, so
nothing has to already exist.

Once the bench is live, use `CLAUDE-PROMPT.md` to put CI/CD on each custom app.

Edit the input block at the top, paste the whole thing into Claude Code.

---

    Create a new Frappe/ERPNext v15 bench on a Dokploy server for a new client,
    as its own Dokploy project, then set up CI/CD for its custom apps.

    === THE INPUT I AM GIVING YOU ===

    Client / company:         <<Acme Coaching>>
    Site domain:              <<erp.acme.com>>
    Frappe / ERPNext branch:  <<version-15>>
    Dokploy server IP:        <<194.146.12.226>>
    Apps to install, in order, as  name|git url|branch :
      <<erpnext|https://github.com/frappe/erpnext.git|version-15>>
      <<hrms|https://github.com/frappe/hrms.git|version-15>>
      <<india_compliance|https://github.com/resilient-tech/india-compliance.git|version-15>>
      <<erp_acme_custom|git@github.com:360ITHUBPVTLTD/erp_acme_custom.git|360ithub_master>>

    Git identity for commits made inside the container:
      name:  <<360ITHub Dev>>
      email: <<dev@360ithub.com>>

    === WHO DOES WHAT ===

    YOU do, through the dokploy MCP - I am not creating anything by hand:
      project-create, compose-create, compose-update (the compose file),
      compose-saveEnvironment (the env vars), domain-create, compose-deploy.

    I do, because you cannot:
      - point the DNS A record at the server, BEFORE you deploy anything
      - grant the deploy-key GitHub account read access to any private repo
      - give you GIT_SSH_KEY_B64 (see below)
      - complete the ERPNext setup wizard at the end

    Ask me for each of these at the moment you need it, not all at the start.

    GIT_SSH_KEY_B64 is the base64 of a private ed25519 deploy key whose public
    half is registered on a GitHub account that can read our private repos. If a
    bench already exists on this server, tell me to copy the value from its
    compose service's Environment tab - the MCP redacts env values so you cannot
    read it yourself. If this is a brand new server, tell me to run, on my laptop:
        ssh-keygen -t ed25519 -f ~/bench_deploy_key -N "" -C "bench@<client>"
        base64 -w0 ~/bench_deploy_key
    and to add ~/bench_deploy_key.pub to the GitHub account as an SSH key.

    === STEP 1: CHECK BEFORE YOU BUILD ANYTHING ===

    a) Confirm the DNS A record for the site domain already resolves to the
       server IP. Let's Encrypt validates over HTTP, so if DNS is not live first
       the certificate fails and the site is stuck on plain HTTP. If it does not
       resolve, tell me and WAIT.

    b) project-all, and confirm the project name and site do not collide with
       something already on this server.

    c) For every private repo in my list, confirm the deploy-key account can read
       it. If not, tell me to grant access before we start - otherwise the clone
       fails several minutes into the build.

    d) Read each custom app's hooks.py and check `required_apps`. Frappe hard-
       fails the install if one is missing and it is easy to leave out of my
       list. Tell me what to add.

    Show me what you found and WAIT for my OK before creating anything.

    === STEP 2: CREATE THE PROJECT, COMPOSE AND ENV ===

    Create the Dokploy project, then a compose service of sourceType "raw", and
    put the compose file below into it verbatim except for the APPS list, which
    you fill in from my input. Keep the app order I gave: dependencies first.

    Then set these with compose-saveEnvironment:
      SITE_NAME, DB_ROOT_PASSWORD, ADMIN_PASSWORD,
      GIT_SSH_KEY_B64, GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL

    Generate DB_ROOT_PASSWORD and ADMIN_PASSWORD yourself, long and random. Do
    NOT print them in the chat. Tell me I can read them in Dokploy under the
    compose service's Environment tab, and that I need ADMIN_PASSWORD to log in
    as Administrator at the end.

    ----- BEGIN COMPOSE FILE -----

    x-bench: &bench
      image: frappe/bench:v5.31.0
      restart: unless-stopped
      working_dir: /home/frappe/frappe-bench
      depends_on:
        init-perms:
          condition: service_completed_successfully
      environment:
        # Pinned deliberately. The image defaults are python 3.14 and node 24,
        # both too new for Frappe v15. pyenv 3.12.14 and nvm v22.23.2 ship in the
        # image; node must come FIRST on PATH.
        PYENV_VERSION: 3.12.14
        PATH: /home/frappe/.nvm/versions/node/v22.23.2/bin:/home/frappe/.pyenv/shims:/home/frappe/.local/bin:/home/frappe/.pyenv/bin:/usr/local/bin:/usr/bin:/bin
        SITE_NAME: ${SITE_NAME}
        DB_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
        ADMIN_PASSWORD: ${ADMIN_PASSWORD}
        GIT_SSH_KEY_B64: ${GIT_SSH_KEY_B64}
        GIT_AUTHOR_NAME: ${GIT_AUTHOR_NAME}
        GIT_AUTHOR_EMAIL: ${GIT_AUTHOR_EMAIL}
        GIT_COMMITTER_NAME: ${GIT_AUTHOR_NAME}
        GIT_COMMITTER_EMAIL: ${GIT_AUTHOR_EMAIL}
      volumes:
        - bench-data:/home/frappe/frappe-bench
        - ssh-data:/home/frappe/.ssh

    services:
      # Docker creates named volumes root-owned, but the image runs as frappe
      # (uid 1000). Fix ownership before anything else touches them.
      init-perms:
        image: frappe/bench:v5.31.0
        user: 0:0
        restart: no
        volumes:
          - bench-data:/home/frappe/frappe-bench
          - ssh-data:/home/frappe/.ssh
        entrypoint: ["bash", "-c"]
        command:
          - |
            chown 1000:1000 /home/frappe/frappe-bench /home/frappe/.ssh
            chmod 700 /home/frappe/.ssh
            echo "permissions ok"

      db:
        image: mariadb:10.6
        restart: unless-stopped
        command:
          - --character-set-server=utf8mb4
          - --collation-server=utf8mb4_unicode_ci
          - --skip-character-set-client-handshake
          - --skip-innodb-read-only-compressed
        environment:
          MARIADB_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
          MARIADB_ROOT_HOST: "%"
        volumes:
          - db-data:/var/lib/mysql
        healthcheck:
          test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
          interval: 10s
          timeout: 5s
          retries: 20

      redis-cache:
        image: redis:6.2-alpine
        restart: unless-stopped
        volumes:
          - redis-cache-data:/data

      redis-queue:
        image: redis:6.2-alpine
        restart: unless-stopped
        volumes:
          - redis-queue-data:/data

      web:
        <<: *bench
        entrypoint: ["bash", "-c"]
        command:
          - |
            # -----------------------------------------------------------------
            # Bench bootstrap. Runs as the entrypoint of the `web` service.
            # Every other bench service waits for the sentinel written at the end.
            # Safe to re-run: each step is guarded, so a redeploy is a no-op once
            # built.
            #
            # To add an app later: add a line to APPS and redeploy, THEN run
            # `bench --site <site> install-app <app>` by hand - the install loop
            # below is behind the sentinel and will be skipped.
            # To force a full asset rebuild: delete sites/.bootstrap-complete.
            # -----------------------------------------------------------------
            set -euo pipefail

            BENCH=/home/frappe/frappe-bench
            SENTINEL="$$BENCH/sites/.bootstrap-complete"

            # name | git url | branch
            # Use git@github.com: for our own repos so `git push` works from
            # inside the container. Dependencies first.
            APPS=(
              "erpnext|https://github.com/frappe/erpnext.git|version-15"
              "hrms|https://github.com/frappe/hrms.git|version-15"
              "india_compliance|https://github.com/resilient-tech/india-compliance.git|version-15"
              "REPLACE_ME|git@github.com:ORG/REPO.git|BRANCH"
            )

            log() { echo "==> [bootstrap $$(date -u +%H:%M:%S)] $$*"; }

            # --- git over ssh, so private repos clone, pull and push ----------
            log "configuring git ssh access"
            mkdir -p "$$HOME/.ssh"
            chmod 700 "$$HOME/.ssh"
            if [ -n "$${GIT_SSH_KEY_B64:-}" ]; then
              printf '%s' "$$GIT_SSH_KEY_B64" | base64 -d > "$$HOME/.ssh/id_ed25519"
              chmod 600 "$$HOME/.ssh/id_ed25519"
            fi
            cat > "$$HOME/.ssh/config" <<'SSHCFG'
            Host github.com
              HostName github.com
              User git
              IdentityFile ~/.ssh/id_ed25519
              IdentitiesOnly yes
              StrictHostKeyChecking accept-new
            SSHCFG
            chmod 600 "$$HOME/.ssh/config"

            # --- wait for datastores ------------------------------------------
            wait_tcp() {
              local host=$$1 port=$$2 tries=0
              until (exec 3<>"/dev/tcp/$$host/$$port") 2>/dev/null; do
                tries=$$((tries + 1))
                if [ "$$tries" -gt 150 ]; then log "FATAL: $$host:$$port never came up"; exit 1; fi
                sleep 2
              done
              log "$$host:$$port is up"
            }
            wait_tcp db 3306
            wait_tcp redis-cache 6379
            wait_tcp redis-queue 6379

            # --- bench itself --------------------------------------------------
            # --ignore-exist because the mounted volume already exists and
            # bench init refuses a non-empty path.
            if [ ! -d "$$BENCH/env" ]; then
              log "initialising bench (first run, takes a few minutes)"
              cd /home/frappe
              bench init --ignore-exist --skip-redis-config-generation --no-backups \
                         --frappe-branch version-15 --verbose frappe-bench
            fi
            cd "$$BENCH"

            # --- point bench at the sibling containers -------------------------
            # developer_mode enables doctype export to app folders, which is what
            # makes the git workflow useful. It is NOT the same as DEV_SERVER,
            # which `bench start` sets and which would make the socket.io client
            # dial :9000 directly and break realtime behind Traefik. That is why
            # we never call `bench start`.
            #
            # webserver_port is deliberately NOT set. frappe's get_url() appends
            # `:<webserver_port>` to every generated link, which would put ":8000"
            # into emails, PDFs and redirects. `bench serve` takes its port from
            # the --port flag below, not from config.
            log "writing common site config"
            bench set-config -g db_host db
            bench set-config -g db_port 3306 --parse
            bench set-config -g redis_cache "redis://redis-cache:6379"
            bench set-config -g redis_queue "redis://redis-queue:6379"
            bench set-config -g redis_socketio "redis://redis-queue:6379"
            bench set-config -g socketio_port 9000 --parse
            bench set-config -g developer_mode 1 --parse

            # --- apps -----------------------------------------------------------
            fetched=0
            for entry in "$${APPS[@]}"; do
              IFS='|' read -r app url branch <<< "$$entry"
              if [ -d "$$BENCH/apps/$$app" ]; then
                continue
              fi
              log "fetching $$app ($$branch)"
              bench get-app --branch "$$branch" --skip-assets "$$app" "$$url"
              fetched=1
            done

            if [ "$$fetched" = "1" ] || [ ! -f "$$SENTINEL" ]; then
              log "building assets for all apps"
              bench build
            fi

            # --- site ------------------------------------------------------------
            if [ ! -d "$$BENCH/sites/$$SITE_NAME" ]; then
              log "creating site $$SITE_NAME"
              bench new-site "$$SITE_NAME" \
                --db-root-username root \
                --db-root-password "$$DB_ROOT_PASSWORD" \
                --admin-password "$$ADMIN_PASSWORD" \
                --mariadb-user-host-login-scope='%' \
                --set-default
            fi

            # Gate on the sentinel, NOT on what this run happened to do. If a
            # previous run was interrupted (e.g. a redeploy during install-app),
            # apps/ and the site dir already exist, so per-run flags would be 0
            # and every remaining app would be silently skipped. install-app
            # early-returns for an already installed app, so re-running the whole
            # loop is safe and cheap.
            if [ ! -f "$$SENTINEL" ]; then
              for entry in "$${APPS[@]}"; do
                IFS='|' read -r app url branch <<< "$$entry"
                log "installing $$app on $$SITE_NAME"
                # A run interrupted mid-install leaves rows behind (e.g. Module
                # Def 'HR' from hrms) without the app being recorded as
                # installed, so a plain retry dies on a duplicate primary key.
                # --force sets ignore_if_duplicate and re-syncs the doctypes,
                # which is frappe's own recovery path.
                if ! bench --site "$$SITE_NAME" install-app "$$app"; then
                  log "$$app install failed; retrying with --force"
                  bench --site "$$SITE_NAME" install-app "$$app" --force
                fi
              done
              # after_migrate hooks that seed records under ERPNext's root trees
              # ("All Customer Groups", "All Item Groups") raise on a fresh site,
              # because those only exist once the setup wizard has been
              # completed - and migrate exits 1 if any after_migrate hook raises.
              # Don't let that stop the site coming up.
              log "running migrations"
              if ! bench --site "$$SITE_NAME" migrate; then
                log "WARNING: migrate exited non-zero (traceback above). Continuing"
                log "WARNING: so the site still serves. Re-run migrate after the wizard."
              fi
            fi

            bench --site "$$SITE_NAME" set-config host_name "https://$$SITE_NAME"
            bench --site "$$SITE_NAME" enable-scheduler || true
            bench use "$$SITE_NAME"

            touch "$$SENTINEL"
            log "bootstrap complete, starting web server on :8000"
            exec bench serve --port 8000
        networks: [default, dokploy-network]

      socketio:
        <<: *bench
        entrypoint: ["bash", "-c"]
        command:
          - |
            until [ -f /home/frappe/frappe-bench/sites/.bootstrap-complete ]; do
              echo "waiting for the web service to finish bootstrapping..."
              sleep 10
            done
            cd /home/frappe/frappe-bench
            exec bench socketio
        networks: [default, dokploy-network]

      scheduler:
        <<: *bench
        entrypoint: ["bash", "-c"]
        command:
          - |
            until [ -f /home/frappe/frappe-bench/sites/.bootstrap-complete ]; do
              echo "waiting for the web service to finish bootstrapping..."
              sleep 10
            done
            cd /home/frappe/frappe-bench
            exec bench schedule

      worker:
        <<: *bench
        entrypoint: ["bash", "-c"]
        command:
          - |
            until [ -f /home/frappe/frappe-bench/sites/.bootstrap-complete ]; do
              echo "waiting for the web service to finish bootstrapping..."
              sleep 10
            done
            cd /home/frappe/frappe-bench
            exec bench worker

      watch:
        <<: *bench
        entrypoint: ["bash", "-c"]
        command:
          - |
            until [ -f /home/frappe/frappe-bench/sites/.bootstrap-complete ]; do
              echo "waiting for the web service to finish bootstrapping..."
              sleep 10
            done
            cd /home/frappe/frappe-bench
            exec bench watch

    volumes:
      bench-data:
      db-data:
      redis-cache-data:
      redis-queue-data:
      ssh-data:

    networks:
      dokploy-network:
        external: true

    ----- END COMPOSE FILE -----

    Note: there are deliberately NO traefik labels in that file. Dokploy
    generates them from the Domains you create in the next step, with router
    names derived from the service's appName. Writing them by hand produces
    duplicate or mismatched routers.

    === STEP 3: DOMAINS ===

    Two domains on the compose service:
      <site>/            -> service web       port 8000   https, letsencrypt
      <site>/socket.io   -> service socketio  port 9000   https, letsencrypt

    CRITICAL: Dokploy has silently set a web domain's port to 8080 after creation
    before. Traefik then emits loadbalancer.server.port 8080 while bench serves
    on 8000, which is a permanent 502 that looks exactly like "still building".
    After creating the domains, read the CONTAINER's traefik labels with
    compose-getConvertedCompose and confirm 8000 and 9000. Do not trust the
    Domains tab.

    === STEP 4: DEPLOY AND WATCH IT ===

    The first build takes several minutes: bench init, get-app per app, bench
    build, new-site, install-app per app, migrate. Tell me how to follow the logs
    and what the normal milestones look like, so I can tell "slow" from "stuck".

    === STEP 5: VERIFY BEFORE HANDING IT OVER ===

    Check and report each of these, do not assume:
      - HTTP 200 on https://<site> with a valid Let's Encrypt certificate
      - window.dev_server is 0   (1 means realtime will break behind Traefik)
      - hashed asset files return 200
      - /socket.io/?EIO=4&transport=polling returns 200
      - http redirects to https
      - every app from my list appears in sites/apps.txt
      - containers: init-perms completed, db healthy, and web, socketio,
        scheduler, worker, watch all up

    === STEP 6: HAND OVER ===

    Tell me to log in as Administrator, complete the ERPNext setup wizard, then
    re-run `bench --site <site> migrate`. Explain why: after_migrate hooks that
    seed records under ERPNext's root trees fail until the wizard has created
    those trees, and migrate exits 1 if any after_migrate hook raises.

    Also tell me once that this bench has NO database backup until I create one
    in Dokploy, and that bench migrate cannot be undone.

    === STEP 7: CI/CD ===

    For each custom app, set up the deploy pipeline. In short:
      - a shared script on the server, /usr/local/bin/deploy-<client>-app.sh,
        taking <app> <branch> <stack> <site>. It pulls inside the web container,
        refuses to run against a dirty working tree, migrates, restarts web,
        worker and scheduler, then polls the site until it answers.
      - a `deploy` user on the server in the docker group, key-only login
      - GitHub Actions calling it over SSH, with DEPLOY_HOST / DEPLOY_USER /
        DEPLOY_SSH_KEY as repo secrets
      - a matrix with fail-fast: false if an app is on several benches
      - a lint gate of ONLY ruff E9,F821,F632,F702 - the full config reports
        hundreds of style findings and makes the pipeline permanently red
      - smoke test one target by hand before turning the workflow on

    The full version of this is docs/CLAUDE-PROMPT.md in the tnc_v2_360ithub
    repo. Use it if you can reach that repo.

    === THINGS YOU MUST KNOW. All of these are real failures we have had. ===

    - Never use `bash -l` in this image. A login shell re-sources .bashrc and
      puts node 24 back on PATH, undoing the pin. Use `bash -c`.
    - Never run `bench start` behind a reverse proxy. It sets DEV_SERVER=true,
      making window.dev_server=1, and frappe's socketio client then dials
      https://<site>:9000 directly instead of the origin. Run each process as its
      own service, as the compose above does.
    - `bench serve` serves /assets and /files itself, so a dev bench needs no
      nginx container. Plain gunicorn on frappe.app:application does not.
    - `bench get-app` names the git remote `upstream`, not `origin`, and clones
      shallow and single-branch. For full history:
      git remote set-branches upstream '*' && git fetch --unshallow upstream
    - Dokploy's Deploy button and auto-deploy webhook redeploy the COMPOSE STACK.
      They cannot deploy app code: the bootstrap skips any app whose folder
      already exists, and an unchanged compose file does not recreate containers
      at all. Use Deploy only for compose file changes.
    - Adding an app to APPS and redeploying FETCHES it but does NOT install it on
      the site, because the install loop is behind the sentinel. Always follow up
      with `bench --site <site> install-app <app>` by hand.

    === HOW TO WORK WITH ME ===

    - Show me your findings and wait for my OK before creating anything.
    - Short numbered steps. One command per step. Always say which machine to run
      it on: my laptop, the Dokploy server, or the container.
    - Tell me what I should see when a step works.
    - Never tell me something is "on your clipboard". xclip does not survive the
      command that set it. Print file contents in full in the chat AND save them
      to a file, and give me the `cat` command for it.
    - Never print a password or a private key. Give me the command that makes it.
    - When you say something works, prove it - status codes, container states,
      the contents of apps.txt. Not "it should be fine".
