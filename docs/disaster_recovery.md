# Disaster Recovery Plan — Smart Reception Server

This document describes how to back up, restore, and recover the Smart
Reception Server in the event of data loss, corruption, hardware failure,
or security incident.

---

## 1. System Overview

| Component       | Location                            | Recovery Class |
| --------------- | ----------------------------------- | -------------- |
| SQLite database | `data/smart_reception.db`           | **Critical**   |
| Face embeddings | DB table `face_embeddings`          | **Critical**   |
| Configuration   | `config.yaml`, `.env`               | High           |
| Logs            | `logs/*.log`                        | Medium         |
| Application code| Git repository                      | Low (rebuildable) |
| Trained models  | `data/models/` (downloaded on demand) | Low          |

Recovery objectives:

- **RPO (Recovery Point Objective):** 24 hours (daily 02:00 backup).
- **RTO (Recovery Time Objective):** 30 minutes from clean disk to
  running server with last good backup.

---

## 2. Backup Strategy

### 2.1 Automated daily backup

Configured in `config.yaml` under `database:`

```yaml
database:
  backup_enabled: true
  backup_interval: daily
  backup_time: "02:00"
  backup_retention_days: 7
```

A scheduled task (Windows Task Scheduler / cron) should run:

```bash
python scripts/backup_database.py backup
python scripts/backup_database.py prune
```

Backups are written to `data/backups/smart_reception_YYYYMMDD_HHMMSS.db`
using SQLite's online backup API (safe while the server is running).

### 2.2 Off-site copy (recommended)

Replicate the `data/backups/` folder to one of:

- An external/USB drive (manually weekly)
- A network share (`robocopy` / `rsync` nightly)
- Encrypted cloud storage (e.g., S3, Backblaze B2) using
  `aws s3 sync` or equivalent

### 2.3 Manual snapshot

On-demand backup before risky operations (migrations, upgrades):

```bash
python scripts/backup_database.py backup
```

### 2.4 Listing & pruning

```bash
python scripts/backup_database.py list
python scripts/backup_database.py prune
```

---

## 3. Restore Procedures

### 3.1 Restore from automated backup

1. Stop the server:
   ```bash
   # Ctrl+C in the uvicorn terminal, or kill the service
   ```
2. Choose the backup file:
   ```bash
   python scripts/backup_database.py list
   ```
3. Restore (the script makes a `pre_restore_*.db` safety copy first):
   ```bash
   python scripts/backup_database.py restore data/backups/smart_reception_20260424_020000.db
   ```
4. Start the server:
   ```bash
   python -m uvicorn server_app:app --host 0.0.0.0 --port 8000
   ```
5. Verify health: `GET /api/v1/health` returns 200 and a row count
   sanity-check on key tables (`guests`, `face_embeddings`, `visits`).

### 3.2 Restore on a fresh machine

1. Install Python 3.14 and clone the repo.
2. Create a venv and install requirements:
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Copy the latest backup `.db` to `data/smart_reception.db`.
4. Copy `config.yaml` and any `.env` from a secure store (these contain
   `SECRET_KEY` and admin credentials — never check them into git).
5. Start the server and verify health as in 3.1 step 5.

### 3.3 Recover from corruption

If `data/smart_reception.db` is corrupt:

```bash
sqlite3 data/smart_reception.db "PRAGMA integrity_check;"
```

If integrity check fails, immediately move the file aside and restore
the most recent good backup (3.1).

---

## 4. Incident Playbooks

### 4.1 Forgotten / lost admin password

1. Stop the server.
2. Open a Python REPL with the project venv active:
   ```python
   from database.connection import SessionLocal
   from database.models import Staff
   from utils.security import hash_password

   db = SessionLocal()
   admin = db.query(Staff).filter_by(username="admin").one()
   admin.password_hash = hash_password("NewStrongPassword!")
   db.commit()
   ```
3. Restart and log in with the new password.

### 4.2 Suspected breach / leaked secret

1. Rotate `SECRET_KEY` in `config.yaml` / environment (this invalidates
   all existing JWT tokens — staff must re-login).
2. Force-rotate all staff passwords (script above for each user, or via
   the admin UI).
3. Review `logs/smart_reception.log` and `system_logs` table for
   suspicious entries (failed logins, IPs).
4. Confirm rate limiting is active on `/api/v1/staff/login`
   (HTTP 429 after 5 failed attempts within 15 minutes per IP).
5. Restore database from a backup taken **before** the suspected breach
   if data tampering is suspected.

### 4.3 Disk failure / total host loss

Follow 3.2 “Restore on a fresh machine” using the most recent off-site
backup. Expected downtime: 20–30 minutes.

### 4.4 Service won't start

Check in order:
1. `logs/smart_reception.log` — most recent traceback.
2. Port 8000 already in use? `Get-NetTCPConnection -LocalPort 8000`.
3. `data/smart_reception.db` permissions / lock file.
4. `config.yaml` syntax (`python -c "import yaml,sys;yaml.safe_load(open('config.yaml'))"`).
5. Run the test suite: `pytest tests/ -v` — green suite confirms code
   integrity, isolating the problem to data/config.

---

## 5. Stability & Health Monitoring

Run the long-soak monitor to validate a deployment:

```bash
python scripts/stability_test.py --hours 8 --interval 60
```

Output: `logs/stability_YYYYMMDD_HHMM.csv` with CPU%, RAM MB / %,
disk %, backend latency, and FPS (pulled from `/api/v1/stats` if
exposed). Alert thresholds:

| Metric            | Warn   | Critical |
| ----------------- | ------ | -------- |
| CPU sustained     | > 75%  | > 90%    |
| RAM used          | > 80%  | > 92%    |
| API p95 latency   | > 1500 ms | > 3000 ms |
| Detector FPS      | < 15   | < 8      |
| Disk free         | < 20%  | < 5%     |

If FPS drops below the critical threshold, see “Performance tuning” in
`README.md` (reduce input resolution, switch face backend to `opencv`,
or disable upselling temporarily).

---

## 5a. HTTPS / TLS

For pilot deployments behind a reverse proxy, terminate TLS at the
proxy. For direct-to-uvicorn HTTPS during development or on-prem
pilots, generate a self-signed certificate:

```bash
python scripts/generate_self_signed_cert.py --host <your-lan-ip> --days 365
uvicorn server_app:app --host 0.0.0.0 --port 8443 \
    --ssl-keyfile certs/server.key --ssl-certfile certs/server.crt
```

Notes:
- Browsers will warn on self-signed certs — import `certs/server.crt`
  into the OS / browser trust store on each kiosk to suppress.
- The `certs/` folder is git-ignored; never commit `server.key`.
- For production, replace with a CA-issued certificate (Let's Encrypt
  via a reverse proxy such as nginx or Caddy is recommended).

---

## 6. Verification Checklist (post-restore)

- [ ] `GET /api/v1/health` returns `200 OK`.
- [ ] Admin can log in via the dashboard.
- [ ] `SELECT COUNT(*) FROM guests;` matches the value recorded the
      morning of the last good backup (within ±1 day of activity).
- [ ] `SELECT COUNT(*) FROM face_embeddings;` matches expected count.
- [ ] At least one known guest is recognized in a live test.
- [ ] `pytest tests/ -v` reports all tests passing.

---

## 7. Contacts & Escalation

| Role              | Responsibility                          |
| ----------------- | --------------------------------------- |
| System Owner      | Approves restores, password rotations   |
| DBA / On-call dev | Performs restore from backup            |
| Security Officer  | Owns breach response (§4.2)             |

Maintain an up-to-date runbook copy off-host (printed and/or in a
separate cloud doc) so this procedure is recoverable even when the
server is not.
