# Windows Lab Automation Portal

Milestone 1: an Ansible/FastAPI foundation for checking WinRM and ensuring one configured test OU exists in an existing Active Directory lab domain. Angular is planned, not implemented in this milestone.

## Status and boundaries

- Lab use only. No domain creation, arbitrary command execution, deletion, backup execution, or VM provisioning endpoints.
- Execution is disabled by default. A health response does not prove connectivity.
- Only one operator-configured server and root-level test OU are supported.
- The original `dist/` files are preserved as legacy examples; this milestone does not repair those old files in place. Use `automation/` for the new workflow.
- Requests execute synchronously in a thread with a 120-second Runner job timeout. Use exactly one API process/worker; its lock is in memory and is not distributed.
- This is not the future durable job service: no database, queue, audit history, streaming events, role-based permissions, or production deployment is included.

## Structure

```text
backend/
  requirements.txt
  app/core.py          # fixed configuration, execution guard, Runner adapter
  app/main.py          # API-key authentication and typed endpoints
  tests/              # mocked unit/API tests; no live server access
automation/
  ansible.cfg
  requirements.yml
  playbooks/connection.yml
  playbooks/test_ou.yml
  roles/test_ou/tasks/main.yml
.env.example          # configuration names; never store real secrets in Git
dist/                 # unchanged legacy site and templates
```

## Prerequisites

Use a Linux control node or Linux environment on your lab management network, Python 3.11 or 3.12, and an existing Windows domain controller with the ActiveDirectory PowerShell module. Configure WinRM HTTPS separately. The chosen account needs permission to connect and manage the test OU. The certificate must match `LAB_HOST` and be trusted by the control node, optionally through `LAB_CA_FILE`.

No bootstrap script is run automatically. Review the legacy bootstrap before using it: it includes relaxed settings that are not defaults of this backend.

## Install

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
ansible-galaxy collection install -r automation/requirements.yml
```

Dependencies are bounded, not locked. Installation and Windows compatibility must be validated in your lab.

## Configure

`.env.example` documents the settings but is not automatically loaded. Export settings into the server process or use your secret manager. For an interactive Bash lab session:

```bash
export LAB_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export LAB_HOST='dc01.lab.example.test'
export LAB_USERNAME='LAB\operator'
export LAB_DOMAIN_DN='DC=lab,DC=example,DC=test'
export LAB_OU_NAME='Portal-Test'
read -rs -p 'Lab password: ' LAB_PASSWORD; echo
export LAB_PASSWORD
# Set this only after reviewing the target and domain:
export LAB_EXECUTION_ENABLED=true
# Optional: export LAB_CA_FILE='/absolute/path/to/lab-ca.pem'
```

The domain DN supports DC components only; the OU name is restricted to a letter followed by letters, digits, or hyphens (maximum 48 characters). Use a new, dedicated test OU name: an existing OU at that identity may have its deletion protection enforced.

## Run locally

```bash
PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Open `http://127.0.0.1:8000/docs`. Do not expose this development API to the internet. Remote access requires TLS and an appropriate authentication/authorization design. No CORS policy for a frontend has been added yet.

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/api/v1/connection-tests \
  -H "X-API-Key: $LAB_API_KEY"
curl -X POST http://127.0.0.1:8000/api/v1/test-ou \
  -H "X-API-Key: $LAB_API_KEY" -H 'Content-Type: application/json' \
  -d '{"confirmation":"CREATE_TEST_OU"}'
```

The OU endpoint checks the connected AD domain, ensures the OU exists with accidental-deletion protection, and then reads it back to verify protection. It does not delete an OU or revert completed changes if verification fails. A connection test does not prove permission to manage AD.

Responses intentionally omit raw Ansible output and credentials. A failed operation returns a generic error; this first milestone does not offer detailed sanitized diagnostics. Runner artifacts are stored in a temporary directory and removed after completion; tasks use `no_log`. Credentials still exist in process memory and temporary inventory during execution, so protect the control node. Abrupt process termination can prevent temporary-directory cleanup.

## Tests and checks

```bash
PYTHONPATH=backend pytest -q backend/tests
cd automation
ansible-playbook -i 'windows_lab,' playbooks/connection.yml --syntax-check
ansible-playbook -i 'windows_lab,' playbooks/test_ou.yml --syntax-check
```

API tests use a stub service and core tests use a fake Runner. Passing them does not establish Windows connectivity or successful OU creation. Live AD verification, Ansible syntax checks, dependency installation, and HTTP integration tests must be run where their dependencies are available.

## Legacy site preview

```bash
python -m http.server 8080 --bind 127.0.0.1 --directory dist
```

Serve `dist/` as the web root because its assets use root-relative paths. The site is not connected to the new API. Do not publish real credentials inside its downloadable files.

## Next milestones

Durable jobs and audit records, stronger identity-based permissions, Angular screens, sanitized event reporting, and broader tested AD workflows. AI assistance is optional future work and must not authorize infrastructure changes.

## License

MIT; see [LICENSE](LICENSE).
