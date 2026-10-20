# PNDMIS — Version 2.1 implementation starter

This is a **Django source-code starter**, not a hosted application and **not approved for production or real staff personal information**.

## What runs
- Login with Django authentication; three roles: supervisor, manager, staff.
- Role-filtered supervisor/manager/staff dashboard, staff directory, LDNI list.
- Staff-owned training entry and document reference submission.
- Manager unit-scoped verification; supervisor approval.
- Shift count entry scoped to the manager's unit.
- Database models for staff 201 metadata, deliverables, LDNI, tasks, shift counts, audit events.
- Unit access tests for cross-unit denial.

## Run locally with fictitious data
1. Install Python 3.11+ and create a virtual environment.
2. `pip install -r requirements.txt`
3. Set `DJANGO_SECRET_KEY` to a long random value; set `DJANGO_DEBUG=True`; set `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`.
4. `python manage.py makemigrations core && python manage.py migrate`
5. `python manage.py createsuperuser` (technical administrator only).
6. `python manage.py runserver` and open `http://127.0.0.1:8000`.
7. In Django admin, create the three Unit records, test users and Profiles. Create sample StaffRecord and Deliverable entries using Django shell or a reviewed seed script; StaffRecord is intentionally not registered in admin.
8. `python manage.py test`.

## Production blockers / necessary work
- Replace SQLite development database with institutionally approved PostgreSQL; configure encrypted transport, secrets management, backups and restore tests.
- Implement identity provider SSO/MFA, password recovery, user provisioning/deprovisioning and session management.
- Complete secured file uploads/downloads with malware scanning, private storage, signed access, file-size/type checks and audit events. **Do not use the document_reference field as a public URL.**
- Implement staff 201 CRUD with field-level access and explicit separation of HR/private data from unit managers.
- Add controlled task and training verification workflows, bulk recurring deliverable generation, scheduled reminders and escalation.
- Add license-expiry notification and approved KPI definitions; actual duty rosters and staff-to-patient ratios are not implemented.
- Enforce review-state transitions in service layer and transactions with row locking; add idempotency and comprehensive tests.
- Implement audit logging for read/download/update/delete actions with immutable log destination and retention controls.
- Complete Philippine Data Privacy Act assessment, data processing agreements, incident response, data retention/deletion and DPO/IT approval.
- Review Django admin permissions: technical administrators currently have administrative capabilities; use separate least-privilege deployment identities.
- Run security audit, penetration testing, accessibility and user acceptance testing before rollout.

## Suggested 12-week delivery
1–2 requirements, indicators and DPO/IT sign-off; 3–4 identity and staff registry; 5–6 submissions and file security; 7–8 LDNI, staffing and reports; 9–10 testing, privacy and training; 11–12 pilot and staged rollout.

**Never import live employee data into this starter.**

---

## Modern SaaS UI (Django — Flask prompt adapted to existing stack)

> Your prompt asked for Flask. Per instruction §8 (inspect existing project, preserve working code), this project **remains Django + SQLite** — the auth, RBAC, audit, and tests already work. The SaaS UI/UX you specified was implemented on top of Django with identical outcomes: HTML5 + CSS3 + vanilla JS, SQLite, Lucide icons, Chart.js, `.venv`, modular code.

### What was built
- **Sidebar (navy #16233a, collapsible, mobile toggle, active states):** Dashboard, Records Management, Categories, Reports & Analytics, 201 Files, Deliverables, LDNI/Training, Deadlines, Shifts, User Management, Settings, Logout.
- **Topbar:** page title + breadcrumb, global search (wired to Records), notification bell, avatar, live Philippine clock (Asia/Manila), mobile hamburger.
- **Dashboard stats (real data only):** Total / Active / Pending / Archived from `Task + Deliverable + StaffRecord`. No fake numbers.
- **Analytics (Chart.js, real `/api/analytics/`):** deliverable-by-status doughnut, staff-per-unit bar, priority breakdown, recent `AuditEvent` list, empty states.
- **Records Management (`/records/` + REST API):** ID, Name, Category (unit), Status, Due, Created, Actions. Search, category/status filter, sorting, pagination (10/page), Add/Edit modal with validation (name ≥3 chars, due required), Delete confirmation modal, toasts, loading spinner, empty state. Every button works.
- **Categories (`/categories/`):** Units with staff/task counts + deliverable-type counts.
- **Reports (`/reports/`):** live charts only.
- **User Management (`/users/`, supervisor only):** Profile role/unit list. Passwords hashed PBKDF2. Create users in `/admin/`.
- **Settings (`/settings/`):** profile, password change, security notes.
- **Security:** session auth + CSRF on all state-changing API calls, server-side validation, RBAC (supervisor=all, manager=own unit, staff=own/assigned), no hardcoded secrets (env/`.env`), ORM parameterized queries.

### REST API
- `GET /api/stats/` → totals/pending/overdue
- `GET /api/analytics/` → by_status, by_unit, by_priority
- `GET /api/records/?search=&category=<unit_id>&status=&sort=name|-name|date|-date|created_at|-created_at|status&page=` → paginated
- `POST /api/records/` {title, description, unit, due_date, priority, status} → 201 / 400 / 403
- `GET|PUT|DELETE /api/records/<id>/` → 200 / 400 / 403 / 404
- Auth: 401 if anonymous, 403 if out-of-scope. CSRF header `X-CSRFToken` required.

### Run on Windows (PowerShell, VS Code)
```powershell
cd C:\laragon\www\PNDMIS
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DJANGO_SECRET_KEY="dev-only-long-random-secret-change-me-1234567890"
$env:DJANGO_DEBUG="True"
$env:DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
# open http://127.0.0.1:8000
python manage.py test -v 2
```

### DB
- SQLite `local_dev.sqlite3` (dev only). Models: Unit, Profile, StaffRecord, Deliverable, Training, Task (now +description/created_at/updated_at/archived), ShiftCount, AuditEvent. Records persist across restarts (file DB, not in-memory).

### Troubleshooting
- `DJANGO_SECRET_KEY is required` → set env or create `.env` from `.env.example`.
- Port 8000 busy → `Get-NetTCPConnection -LocalPort 8000` then `Stop-Process -Id <pid>`.
- Static CSS 404 → ensure `DEBUG=True` + `django.contrib.staticfiles` installed; hard-refresh.
- 403 on API → login + check role (staff cannot create/delete; manager unit-scoped).
- Charts empty → create Tasks/Deliverables first; API returns `[]`, UI shows empty state by design.

**Never import live employee data into this starter.**
