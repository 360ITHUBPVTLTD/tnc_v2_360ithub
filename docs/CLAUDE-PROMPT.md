# The Prompt

Copy the whole block below into Claude Code.

**Change only the two lines at the top** — the repo and the branch. Claude works
out everything else itself, including which benches the app is on.

---

```
Set up CI/CD for this Frappe custom app. Every push to the branch below must
automatically deploy it to EVERY bench that has this app installed.

=== THE ONLY INPUT I AM GIVING YOU ===

GitHub repo:  <<360ITHUBPVTLTD/my_app>>
Branch:       <<360ithub_master>>

Work out everything else yourself, then confirm it with me before changing
anything.

=== STEP 1: DISCOVER. Change nothing yet. ===

a) Read the repo. The app name is the directory that contains hooks.py.

b) Use the dokploy MCP to find EVERY bench that has this app installed:
   - project-all to list all projects and their compose services
   - compose-getConvertedCompose on each one, then look inside the bootstrap
     script's APPS=( ... ) list for this app name
   For each match, record: project name, composeId, stack appName, SITE_NAME,
   the domain, and serverId.

c) docker-getContainersByAppNameMatch on each stack to confirm it is running.

d) Print a table of every target you found:
       project | stack | site | running?
   Then STOP and ask me to confirm before you change anything.

If the app is on NO bench yet, tell me the exact line to add to the APPS=( )
list in the compose file, and remind me that after clicking Deploy in Dokploy I
must still run `bench --site <site> install-app <app>` BY HAND. The bootstrap
downloads the app but does not install it, because the install loop sits behind
`if [ ! -f "$SENTINEL" ]` and that sentinel already exists on a working bench.
It fails silently.

=== STEP 2: WHAT ALREADY EXISTS. Do not rebuild these. ===

- Dokploy server 194.146.12.226, with a `deploy` user in the docker group,
  key-only login.
- /usr/local/bin/deploy-tnc-app.sh on that server. It already pulls, migrates,
  restarts web/worker/scheduler, and health-checks the site.
- SSH keypair: private key at ~/tncv2_deploy on my laptop, public key already in
  /home/deploy/.ssh/authorized_keys on the server.
- A working reference to copy from: the tnc_v2_360ithub repo - see
  .github/workflows/deploy.yml, deploy/deploy-tnc-app.sh and docs/.

=== STEP 3: MULTIPLE BENCHES IS THE POINT ===

The same app is often installed on several Dokploy projects. The deploy must
handle N targets, not one.

- deploy-tnc-app.sh ALREADY takes the target as arguments:
      deploy-tnc-app.sh <app> <branch> <stack> <site>
  Stack and site default to the tncv2 bench when omitted. Do not change the
  script. If the copy on the server is older than this, tell me to run:
      scp ~/tncv2-cicd/deploy-tnc-app.sh root@194.146.12.226:/usr/local/bin/deploy-tnc-app.sh

- The workflow must deploy to every target with a matrix:
      strategy:
        fail-fast: false
        matrix:
          include:
            - stack: <stack-1>
              site:  <site-1>
            - stack: <stack-2>
              site:  <site-2>

  fail-fast: false matters. If one client's bench is down I still want the
  others deployed.

- Keep `concurrency` grouped per app so two pushes never overlap.

- All targets on the same server share the same DEPLOY_HOST / DEPLOY_USER /
  DEPLOY_SSH_KEY secrets. Only stack and site differ. If you find a target with a
  different serverId, tell me - that one needs its own host secret and its own
  key installed.

=== STEP 4: WHAT TO GIVE ME ===

1. The .github/workflows/deploy.yml with the matrix filled in from what you
   found in Step 1. Start from docs/deploy.yml.template in the tnc_v2_360ithub
   repo - it already has the matrix shape.
2. Exactly which GitHub secrets to add, and where.
3. One command to smoke test a SINGLE target before I turn anything on.
4. How to verify afterwards that the code landed on EVERY target.

=== THINGS YOU MUST KNOW ABOUT THIS SETUP ===

- Three machines are involved: my laptop, the Dokploy server (194.146.12.226),
  and the container inside it. Label every single command with which one to run
  it on. I get this wrong otherwise.
- `bench get-app` names the git remote `upstream`, NOT `origin`.
- Dokploy's Deploy button and its auto-deploy webhook CANNOT deploy app code.
  They only redeploy the compose stack, and the bootstrap skips any app whose
  folder already exists. App code lives on the bench-data volume, below what
  Dokploy manages.
- The lint gate must use only ruff rules E9,F821,F632,F702. The full ruff config
  reports hundreds of style findings and would make the pipeline permanently red.
- The deploy script runs from /usr/local/bin on the server. Editing the copy in
  the git repo changes nothing until it is scp'd across.
- A green tick only means the script exited 0. Verify with container restart
  times and the commit SHA on the server.
- If this app ships custom/*.json files: removing a Customize Form field does
  NOT work through the JSON alone, because bench migrate never deletes custom
  fields. Add the reconcile_custom_fields after_migrate hook as well, copying
  tnc_v2_360ithub/customizations.py. Tell me it reports before it deletes and
  that I must arm it per site.
- This bench has NO database backup and bench migrate cannot be undone. Mention
  this once if you are setting up a new bench.

=== HOW TO WORK WITH ME ===

- Show me the discovered target list and wait for my OK before changing anything.
- Short numbered steps. One command per step. Always say which machine.
- Tell me what I should see when a step works.
- Do not push to my default branch. Open a pull request.
```

---

## After it is set up

Short follow-ups you can paste any time. Same rules apply — Claude already has
the context from the prompt above if you are in the same session.

**A deploy failed:**

```
The deploy for <<my_app>> failed. Here is the log:

<<paste>>

Check the real state on the server before answering - the log is often
truncated by bench migrate's progress bars, so do not guess from it alone.
```

**A removed custom field is still on the site:**

```
I removed a custom field from <<my_app>> with Customize Form, exported, and
merged. The field is still on the site. Fix this properly - no hardcoded field
names, it must work for every add and remove from now on.
```

**Add a backup (do this one soon):**

```
Our Dokploy bench has no backup at all and we have automated bench migrate
against it. Set up a daily database backup, and tell me how to test that a
restore actually works.
```

**Add the app to one more bench:**

```
<<my_app>> now also needs to deploy to <<project name>>. Find that bench, add it
to the workflow matrix, and tell me anything I need to do on the server first.
```
