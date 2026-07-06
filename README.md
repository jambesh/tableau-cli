# tab-cli

**Application:** Tableau-CLI · **Version:** 1.0 · **Language:** Python 3.10+ · **License:** GPL-3.0

A friendlier command line for **Tableau Server / Tableau Cloud** daily operations.

Tableau ships `tabcmd`, but it lacks everyday conveniences an admin actually
wants — like browsing a project's contents as a **tree**, moving a workbook
between projects, renaming things, or changing ownership without hunting for
GUIDs. `tab-cli` fills those gaps. It is built on Tableau's official
[`tableauserverclient`](https://tableau.github.io/server-client-python/) (the
same REST-API layer the modern `tabcmd` uses), so it works against both Tableau
Server and Tableau Cloud.

```
$ tab-cli ls Finance --owner
📁 Finance
├── 📁 Reports
│   ├── 📁 2026
│   └── 📊 Budget            owner: alice
├── 📊 Sales Dashboard       owner: bob
└── 🗃️  Ledger               owner: alice
2 sub-project(s), 2 workbook(s), 1 data source(s)
```

---

## Install

```bash
git clone https://github.com/jambesh/tableau-cli
cd tableau-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -e .          # installs the `tab-cli` command
```

> Requires Python **3.10+** (a constraint of the current `tableauserverclient`).

## Authenticate

Sign in **once**; the session token is cached (0600) under `~/.tabcli/` and
reused by every later command. Because a Tableau personal access token allows
only one active session, `tab-cli` reuses the cached token rather than
re-signing-in each time, and transparently refreshes it when it expires.

```bash
# Personal Access Token (recommended)
tab-cli login -s https://10ax.online.tableau.com \
              --token-name my-token --token-value <SECRET> \
              --site MarketingSite

# Username / password
tab-cli login -s https://tableau.mycompany.com -m password -u alice --site ""
```

Any prompt you omit is asked interactively (secrets are hidden). Verify and end
a session with:

```bash
tab-cli whoami      # who am I, on which site
tab-cli status      # local config/session state (no network call)
tab-cli logout      # invalidate + clear the cached session
```

### Non-interactive / CI use

Every config value can come from an environment variable instead of disk — pass
`--no-save-secret` at login (or skip `login` entirely) and export:

| Variable | Purpose |
|---|---|
| `TABCLI_SERVER` | Server URL |
| `TABCLI_SITE` | Site content URL (`""` = Default) |
| `TABCLI_AUTH_METHOD` | `pat` or `password` |
| `TABCLI_TOKEN_NAME` / `TABCLI_TOKEN_VALUE` | PAT credentials |
| `TABCLI_USERNAME` / `TABCLI_PASSWORD` | password credentials |
| `TABCLI_SSL_NO_VERIFY` | set to disable TLS verification |
| `TABCLI_HOME` | override the `~/.tabcli` state directory |

---

## Commands

Global flags: `--json` (machine-readable output on stdout), `--no-color`.

### Browse — `ls`

```bash
tab-cli ls                      # top-level projects of the site
tab-cli ls Finance              # tree of one project
tab-cli ls "Finance/Reports"    # address nested projects by path
tab-cli ls Finance --owner      # annotate items with their owner
tab-cli ls Finance --projects-only --depth 2
tab-cli ls Finance --workbooks-only
tab-cli --json ls Finance       # nested JSON for scripting
```

Project names repeat across the site, so anywhere a project is expected you can
pass either a **name** (resolved uniquely, or it lists the candidates) or a
full **`Parent/Child`** path.

### Projects — `project`

```bash
tab-cli project list [--top]
tab-cli project create "New Project" --parent Finance --description "..."
tab-cli project rename "Old Name" "New Name"
tab-cli project move   Reports Finance          # re-parent
tab-cli project move   Reports --to-root
tab-cli project chown  Finance alice            # change owner
tab-cli project delete Finance --yes
tab-cli project info   Finance
```

### Workbooks — `workbook`

```bash
tab-cli workbook list [--project Finance]
tab-cli workbook download "Sales Dashboard" -o ./out/       # .twbx (+extract)
tab-cli workbook download "Sales Dashboard" --no-extract
tab-cli workbook rename   "Sales Dashboard" "Sales v2"
tab-cli workbook move     "Sales v2" Archive                # between projects
tab-cli workbook chown    "Sales v2" alice
tab-cli workbook refresh  "Sales v2" --wait                 # trigger extract refresh
tab-cli workbook delete   "Sales v2" --yes
```

Add `--project <name>` to any workbook command to disambiguate identically named
workbooks in different projects.

### Data sources — `datasource`

```bash
tab-cli datasource list [--project Finance]
tab-cli datasource download "Ledger" -o ./out/
tab-cli datasource rename   "Ledger" "Ledger 2026"
tab-cli datasource move     "Ledger 2026" Archive
tab-cli datasource chown    "Ledger 2026" alice
tab-cli datasource refresh  "Ledger 2026" --wait
tab-cli datasource delete   "Ledger 2026" --yes
```

### Views — `view`

```bash
tab-cli view list [--workbook "Sales Dashboard"]
tab-cli view download-image "Overview" --workbook "Sales Dashboard" -o ./img/
tab-cli view download-pdf   "Overview" -o ./out/
tab-cli view download-csv   "Overview" -o ./out/            # summary data
```

### Jobs — `job`

```bash
tab-cli job list --limit 25       # recent background jobs (refreshes, etc.)
tab-cli job wait <job-id>         # block until a job finishes
```

### Groups — `group`

```bash
tab-cli group list
tab-cli group create "Analysts"                                   # local group
tab-cli group import-ad "Analysts" --domain CORP --site-role Explorer
```

---

## How it fits together

```
tabcli/
├── cli.py            # root click group, global flags, error boundary
├── config.py         # ~/.tabcli config + session cache (0600 files, env overrides)
├── session.py        # sign-in, token caching/reuse, transparent re-auth
├── resolve.py        # name/path → project/workbook/datasource/user resolution
├── output.py         # rich tree + tables + JSON rendering
└── commands/         # one module per command group
    ├── auth.py  ls.py  project.py  workbook.py
    ├── datasource.py   view.py     job.py       group.py
```

## Notes & safety

- Credentials and the session token live in `~/.tabcli/` with `0600`
  permissions. They are **git-ignored** — never commit them.
- Destructive commands (`delete`) prompt for confirmation unless you pass
  `--yes`.
- Expected errors are printed as a single clean line (no Python traceback);
  exit code is non-zero on failure, so it composes well in scripts.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
