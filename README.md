# Database Backup & Restore (SQLite, MySQL, PostgreSQL, MSSQL)

A Python-based backup & restore system supporting:

- SQLite
- MySQL / MariaDB
- PostgreSQL
- Microsoft SQL Server
- Multiple instances
- Docker & non-Docker databases
- Per-database backups (even when backing up “all databases”)
- Safe online backups
- Configurable retention
- Restore to same or different database names

Designed for self-hosted servers, NAS (tested on Synology), and Docker environments.

## Features

### General
- YAML-based configuration (`config.yml`)
- Timestamped backups (`YYYYMMDD_HHMMSS`)
- Automatic retention cleanup (default: 10 backups)
- Works while databases are **in use**
- Supports multiple database instances

### SQLite
- Uses SQLite **online backup API** (`.backup`)
- Safe for live databases
- Folder structure:
  ```
  backups/sqlite/<instance_name>/<db_name>_<timestamp>.sqlite
  ```

### MySQL / MariaDB
- Supports:
  - Docker container databases
  - Remote TCP databases (via Docker image)
- Per-database backups even when backing up all DBs
- Gzipped backups
- Silent (no password warnings)
- Folder structure:
  ```
  backups/mysql/<instance>/<timestamp>/<database>.sql.gz
  ```

### PostgreSQL
- Supports:
  - Docker container databases
  - Remote TCP databases (via Docker image)
- Per-database backups using `pg_dump`
- Custom format (`.dump`)
- Folder structure:
  ```
  backups/postgresql/<instance>/<timestamp>/<database>.dump
  ```

### Microsoft SQL Server
- Supports:
  - Docker container databases
  - Remote TCP databases (via Docker image)
- Per-database backups even when backing up all DBs
- Silent (no password warnings)
- Folder structure:
  ```
  backups/mssql/<instance>/<timestamp>/<database>.bak
  ```

## Requirements

### System
- Python **3.8+**
- Docker (required for `tcp_docker` mode)
- Installed locally OR available in Docker:
  - `sqlite3` for SQLite
  - `mysqldump` for MySQL/MariaDB
  - `pg_dump` for PostgreSQL
  - `sqlcmd` for MSSQL

### Python packages
```bash
pip install pyyaml
```

or 

```bash
pip install -r requirements.txt
```

## Configuration (`config.yml`)

### Backup settings
```yaml
backup:
  output_dir: backups
  retention: 10
```

### SQLite example
```yaml
sqlite:
  enabled: true
  instances:
    - name: calibre
      databases:
        - name: calibre
          path: /data/calibre/calibre.db
```

### MySQL / MariaDB example
```yaml
mysql:
  enabled: true
  instances:
    - name: ryzen9-mariadb
      mode: tcp_docker
      host: 192.168.1.5
      port: 3306
      user: root
      password: secret
      image: mariadb:10
      databases:
        - romm
        - paperless
```

### PostgreSQL example
```yaml
postgresql:
  enabled: true
  instances:
    - name: ryzen9-postgresql
      mode: tcp_docker
      host: 192.168.1.6
      port: 5432
      user: postgres
      password: secret
      image: postgres:16
      databases: []   # empty = backup ALL databases separately
```

### MySQL / MariaDB example
```yaml
mssql:
  enabled: true
  instances:
    - name: ryzen9-mssql
      mode: tcp_docker
      host: 192.168.1.5
      port: 1433
      user: root
      password: secret
      image: mcr.microsoft.com/mssql-tools
      databases:
        - sales
        - inventory
```

## Connection / Backup Modes

Each MySQL, PostgreSQL, and MSSQL instance must define a `mode` that determines how the backup and restore process connects to the database.

### `docker` mode

Use this when the database is running inside a local Docker container on the same machine.

The script executes backup commands directly inside the container using `docker exec`.

Requirements:
- Docker installed
- Database container running locally
- Dump utilities available inside the container

Example:
```yaml
mode: docker
docker_container: mariadb
```

How it works:
- MySQL: docker exec <container> mysqldump
- PostgreSQL: docker exec <container> pg_dump
- MSSQL: docker exec <container> sqlcmd

### `tcp_docker` mode (recommended for remote databases)

Use this when the database is on another machine or host, and dump tools are NOT installed locally.

The script runs a temporary Docker container containing the correct client tools and connects over TCP.

Requirements:
- Docker installed on the backup machine
- Database accessible via host + port

Example:
```yaml
mode: tcp_docker
host: 192.168.8.5
port: 11010
image: mysql:8
```

How it works:
- Starts a temporary Docker container
- Uses mysqldump or pg_dump from the image
- Connects to the remote database
- Container is removed after completion

### `tcp` mode (host-installed tools)

Use this only if the dump utilities are installed on the host system.

Requirements:
- mysqldump / pg_dump installed locally
- Database reachable over TCP

Example:
```yaml
mode: tcp
host: 127.0.0.1
port: 3306
```

How it works:
- Runs dump utilities directly on the host
- Connects to the database over TCP

## Running Backups

```bash
python backup.py
```

## Restore Usage

```bash
python restore.py <engine> <instance> <backup_file> <mode> [source_db] [target_db]
```

> You may need sudo to backup and restore mysql/mariadb/postgresql in tcp_docker mode

### Restore Example

```bash
python restore.py postgresql ryzen9-postgresql backups/postgres
ql/ryzen9-postgresql/radarr-main_20251216_131710.dump single radarr-main radarr-restored
```

## Backup Structure Example

```
backups/
├── sqlite/
│   └── calibre/
│       └── calibre_20251216_131710.sqlite
│
├── mysql/
│   └── ryzen9-mariadb/
│       └── 20251216_131710/
│           ├── romm.sql.gz
│           └── paperless.sql.gz
│
├── postgresql/
│   └── ryzen9-postgresql/
│       └── 20251216_131710/
│           ├── postgres.dump
│           └── n8n.dump
│
└── mssql/
    └── ryzen9-mssql/
        └── 20251216_131710/
            ├── sales.bak
            └── inventory.bak
```

## Docker Image Compatibility (Important)

When using **Docker-based backup or restore modes** (`tcp_docker`), it is **strongly recommended** to use the **same Docker image (or at least the same major version)** as the source database.

### Why this matters

Database dump and restore tools are **not always fully backward- or forward-compatible**, especially across major versions.

Examples:
- `mysqldump` from MySQL 8 restoring into MariaDB 10.x
- `pg_dump` from PostgreSQL 16 restoring into PostgreSQL 12
- Differences in:
  - SQL syntax
  - Default character sets & collations
  - Index / constraint behavior
  - Feature support (events, routines, extensions)

Using a mismatched image can result in:
- Empty restores
- Missing tables
- Silent failures
- Restore errors that only appear at runtime

### Best Practice

Always match the image version to the **target database version**:

```yaml
mysql:
  instances:
    - name: prod-mariadb
      mode: tcp_docker
      image: mariadb:10.11
```

If exact matching is not possible:
- Keep major versions the same
- Test restore on a non-production database first

## TODO
- [ ] Logging/log file
- [ ] Create a docker image with cron scheduling
- [ ] Create a UI

## Disclaimer
Parts of this project (mainly refactoring and parts of readme) was created with the help of ChatGPT. All the logic, structure, and almost the whole chunk of the codes are created by me and tested in my own environment.

## License
MIT – use at your own risk.