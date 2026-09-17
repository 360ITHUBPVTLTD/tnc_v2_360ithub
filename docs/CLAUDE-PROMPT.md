# Prompts to give Claude

Copy a prompt below, replace the `<<...>>` parts with your values, and paste it
into Claude Code.

Everything Claude needs to know about our setup is already written into these
prompts, so it does not have to work it out again and cannot guess wrong.

---
---

# PROMPT 1 — Set up CI/CD for a new app

**Use this for:** a brand new custom app that has no automatic deploy yet.

**Edit these 5 lines before pasting:** app name, repo, branch, site, stack.

```
Set up CI/CD for a Frappe custom app on our Dokploy bench, so that pushing to
the branch deploys it automatically.

MY APP
- App name (python package): <<my_new_app>>
- GitHub repo:               <<360ITHUBPVTLTD/my_new_app>>
- Branch to deploy:          <<360ithub_master>>
- Site:                      <<tncv2.360ithub.com>>
- Dokploy stack (appName):   <<test-demo-erpnext-w6y5gf>>
- Dokploy server:            194.146.12.226

WHAT ALREADY EXISTS - do not create these again
- A `deploy` user on the server, in the docker group, key-only login.
- /usr/local/bin/deploy-tnc-app.sh on the server. It is generic and takes
  <app> <branch> as arguments, so it already works for any app on this bench.
- The SSH keypair: private key at ~/tncv2_deploy on my laptop, public key
  already in /home/deploy/.ssh/authorized_keys on the server.
- A working example to copy from: the tnc_v2_360ithub repo.

WHAT I WANT
1. Check whether my app is already on the bench. If it is not, tell me the
   exact line to add to the APPS=( ) list in the Dokploy compose file, and
   remind me I must then run `bench install-app` by hand.
2. Give me the .github/workflows/deploy.yml for my app, ready to paste.
3. Tell me exactly which GitHub secrets to add and where.
4. Give me the one command to smoke test it before I turn it on.
5. Tell me how to verify afterwards that the code really landed on the server.

THINGS YOU MUST KNOW ABOUT THIS SETUP
- There are three machines: my laptop, the Dokploy server (194.146.12.226), and
  the container inside it. Label every command with which one to run it on. I
  get this wrong otherwise.
- The bench bootstrap FETCHES a newly added app but does NOT install it on the
  site, because the install loop is behind `if [ ! -f "$SENTINEL" ]` and the
  sentinel already exists. It fails silently. Always remind me about this.
- `bench get-app` names the git remote `upstream`, NOT `origin`.
- Dokploy's Deploy button and its auto-deploy webhook CANNOT deploy app code.
  They only redeploy the compose stack. App code lives on the bench-data volume.
- The lint step must only use ruff rules E9,F821,F632,F702. The full ruff config
  reports hundreds of style findings and would make the pipeline permanently red.
- The deploy script runs from /usr/local/bin on the server. Editing the copy in
  the git repo changes nothing until it is scp'd across.

HOW TO WORK WITH ME
- Give me short numbered steps, not long explanations.
- One command per step, and say which machine to run it on.
- Tell me what I should see when a step works.
- Wait for me to confirm a step before moving to the next one.
```

---
---

# PROMPT 2 — Removing a Customize Form field does not work

**Use this for:** you removed a field, exported, merged, and it is still on the
site.

```
I removed a custom field from my Frappe app using Customize Form, exported the
customizations, committed and merged. The deploy went green but the field is
still on the server.

MY APP
- App name: <<my_new_app>>
- Repo:     <<360ITHUBPVTLTD/my_new_app>>
- Site:     <<tncv2.360ithub.com>>

I know the cause: bench migrate's sync_customizations only inserts and updates
custom fields, it never deletes one that was removed from the JSON.

We already solved this in the tnc_v2_360ithub repo, in
tnc_v2_360ithub/customizations.py (reconcile_custom_fields, registered as the
LAST after_migrate hook). Please adapt that same solution for my app.

Do not hardcode any field names. It must work for every add and remove from now
on, automatically.

Before I merge it, show me how to preview what it would delete, because deleting
a custom field drops its database column and destroys data.
```

---
---

# PROMPT 3 — Set up CI/CD on a different client's bench

**Use this for:** a new client server, not the TNC one.

```
Set up CI/CD for a Frappe custom app on a DIFFERENT client bench. We already
have this working for tncv2.360ithub.com and I want the same thing here.

THE NEW CLIENT
- Dokploy server IP:   <<1.2.3.4>>
- Dokploy stack:       <<client-stack-name>>
- Site:                <<erp.client.com>>
- App name:            <<erp_client_custom>>
- GitHub repo:         <<360ITHUBPVTLTD/erp_client_custom>>
- Branch:              <<360ithub_master>>

WHAT TO COPY FROM
The tnc_v2_360ithub repo has: deploy/deploy-tnc-app.sh, the workflow in
.github/workflows/deploy.yml, and docs/CICD-GUIDE.md.

IMPORTANT
- deploy-tnc-app.sh HARDCODES STACK and SITE at the top. For this client, make a
  separate copy at /usr/local/bin/deploy-<<client>>-app.sh with the new values.
  Do not parameterise it - deploying to the wrong client's site is a bad failure.
- This is a new server, so the one-time setup is needed too: create the `deploy`
  user, install the script, create and install an SSH key.
- Give me short numbered steps and label every command with which machine to run
  it on: my laptop, the client's server, or the container.
```

---
---

# PROMPT 4 — A deploy failed and I do not understand why

```
A deploy failed for my Frappe app and I need help reading it.

- App:   <<my_new_app>>
- Repo:  <<360ITHUBPVTLTD/my_new_app>>
- Site:  <<tncv2.360ithub.com>>
- Stack: <<test-demo-erpnext-w6y5gf>>
- Server: 194.146.12.226

Here is what the Actions log said:

<<paste the error here>>

Please check the real state on the server before telling me what is wrong - do
not guess from the log alone. A green tick only means the script exited 0, and
the log often gets truncated by bench migrate's progress bars.

Useful facts:
- container restart times tell you whether the script reached the restart step
- the app's commit SHA on the server tells you whether the code actually landed
```

---
---

# PROMPT 5 — Add a database backup

**Do this one soon.** We currently have no backup at all, and `bench migrate`
cannot be undone.

```
Our Dokploy bench has no backup of any kind - no compose backup, no volume
backup, no schedule - and we have just automated bench migrate against it. A bad
migration would have nothing to restore from.

- Dokploy server: 194.146.12.226
- Stack:          <<test-demo-erpnext-w6y5gf>>
- Site:           <<tncv2.360ithub.com>>
- Database:       mariadb 10.6, running as the `db` service in the compose stack

Set up a daily automatic backup. Tell me what I need to provide (for example S3
credentials, or a local path) and walk me through it in short numbered steps,
saying which machine to run each command on.

Also tell me how to test that a restore actually works. A backup nobody has
restored from is not a backup.
```

---
---

# How to write your own prompt

If none of the above fits, include these four things and Claude will do well:

| Include | Why |
|---|---|
| **Your values** — app, repo, branch, site, stack, server | Otherwise it guesses or asks |
| **What already exists** — deploy user, the script, the SSH key | Stops it rebuilding things |
| **The gotchas** — the install-app trap, `upstream` not `origin`, Dokploy's button not deploying code | Stops it repeating mistakes we already paid for |
| **How you want to be told** — short numbered steps, one command each, labelled by machine | This is the difference between a usable answer and a wall of text |

**Two sentences worth adding to almost any prompt:**

```
Label every command with which machine to run it on: my laptop, the Dokploy
server, or the container. Give me short numbered steps and wait for me to
confirm each one before moving on.
```
