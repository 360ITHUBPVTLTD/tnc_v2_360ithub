# Docs

## Start here

| File | What it is | Length |
|---|---|---|
| **SIMPLE-STEPS** | Set up CI/CD for a new app. Just the steps. | 4 pages |
| **CLAUDE-PROMPT** | Prompt for putting CI/CD on an app that already has a bench. Edit the `<<...>>` parts. | 4 pages |
| **NEW-BENCH-PROMPT** | Prompt for creating a whole new client bench from scratch, then its CI/CD. | 4 pages |
| CICD-GUIDE | Full reference. Read only when something is not covered above. | 21 pages |

Each one has a `.md` (read on GitHub) and a `.docx` (share with people).

## Other files

| File | What it is |
|---|---|
| `deploy.yml.template` | The workflow file to copy into a new app's repo |
| `md2docx.py` | Regenerates the `.docx` files from the `.md` files |

## Regenerating the Word files

After editing any `.md`, run:

```bash
pip install python-docx
python3 docs/md2docx.py docs/SIMPLE-STEPS.md  docs/CICD-Simple-Steps.docx
python3 docs/md2docx.py docs/CLAUDE-PROMPT.md docs/CICD-Claude-Prompts.docx
python3 docs/md2docx.py docs/CICD-GUIDE.md    docs/CICD-Guide-TNC-Bench.docx
```

The `.md` is the source of truth. The `.docx` is generated — never edit it directly.
