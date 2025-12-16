import os
import yaml
import subprocess
import shutil
import gzip
from datetime import datetime
from pathlib import Path

CONFIG_FILE = "config.yml"

with open(CONFIG_FILE) as f:
    config = yaml.safe_load(f)

BACKUP_ROOT = Path(config["backup"].get("output_dir", "backups"))
RETENTION = config["backup"].get("retention", 10)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def rotate_folders(base: Path):
    folders = sorted(
        [p for p in base.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime
    )

    while len(folders) > RETENTION:
        old = folders.pop(0)
        print(f"Deleting old backup folder: {old}")
        shutil.rmtree(old)


def rotate_files(base: Path):
    files = sorted(
        [p for p in base.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime
    )

    while len(files) > RETENTION:
        old = files.pop(0)
        print(f"Deleting old backup file: {old}")
        old.unlink()

def backup_sqlite():
    if not config.get("sqlite", {}).get("enabled"):
        return

    base = BACKUP_ROOT / "sqlite"
    ensure_dir(base)

    for inst in config["sqlite"]["instances"]:
        inst_dir = base / inst["name"]
        ensure_dir(inst_dir)

        db_path = inst["path"]

        outfile = inst_dir / f"{inst['name']}_{TIMESTAMP}.sql.gz"

        print(f"Backing up SQLite {inst['name']}")

        dump = subprocess.Popen(
            ["sqlite3", db_path, ".dump"],
            stdout=subprocess.PIPE
        )

        with gzip.open(outfile, "wb") as f:
            shutil.copyfileobj(dump.stdout, f)

        dump.wait()

        rotate_files(inst_dir)

def backup_mysql():
    if not config.get("mysql", {}).get("enabled"):
        return

    base = BACKUP_ROOT / "mysql"
    ensure_dir(base)

    for inst in config["mysql"]["instances"]:
        inst_dir = base / inst["name"]
        ensure_dir(inst_dir)

        ts_dir = inst_dir / TIMESTAMP
        ensure_dir(ts_dir)

        image = inst.get("image", "mysql:8")

        databases = inst.get("databases") or get_mysql_databases(inst, image)

        for db in databases:
            outfile = ts_dir / f"{db}.sql.gz"

            print(f"Backing up MySQL [{inst['name']}]: {db}")

            cmd = [
                "docker", "run", "--rm",
                image,
                "mysqldump",
                "--column-statistics=0",
                "-h", inst["host"],
                "-P", str(inst.get("port", 3306)),
                "-u", inst["user"],
                f"-p{inst['password']}",
                "--single-transaction",
                "--quick",
                "--routines",
                "--events",
                db
            ]

            dump = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            with gzip.open(outfile, "wb") as f:
                shutil.copyfileobj(dump.stdout, f)

            dump.wait()

        rotate_folders(inst_dir)


def get_mysql_databases(inst, image):
    cmd = [
        "docker", "run", "--rm",
        image,
        "mysql",
        "-h", inst["host"],
        "-P", str(inst.get("port", 3306)),
        "-u", inst["user"],
        f"-p{inst['password']}",
        "-N",
        "-e", "SHOW DATABASES"
    ]

    result = subprocess.check_output(
        cmd,
        text=True,
        stderr=subprocess.DEVNULL
    )
    dbs = [
        d for d in result.splitlines()
        if d not in ("information_schema", "mysql", "performance_schema", "sys")
    ]
    return dbs

def backup_postgresql():
    if not config.get("postgresql", {}).get("enabled"):
        return

    base = BACKUP_ROOT / "postgresql"
    ensure_dir(base)

    for inst in config["postgresql"]["instances"]:
        inst_dir = base / inst["name"]
        ensure_dir(inst_dir)

        ts_dir = inst_dir / TIMESTAMP
        ensure_dir(ts_dir)

        image = inst.get("image", "postgres:16")

        databases = inst.get("databases") or get_postgres_databases(inst, image)

        for db in databases:
            outfile = ts_dir / f"{db}.dump"

            print(f"Backing up PostgreSQL [{inst['name']}]: {db}")

            cmd = [
                "docker", "run", "--rm",
                "-e", f"PGPASSWORD={inst['password']}",
                image,
                "pg_dump",
                "-Fc",
                "-h", inst["host"],
                "-p", str(inst.get("port", 5432)),
                "-U", inst["user"],
                "-d", db
            ]

            subprocess.run(cmd, stdout=open(outfile, "wb"), check=True)

        rotate_folders(inst_dir)

def get_postgres_databases(inst, image):
    cmd = [
        "docker", "run", "--rm",
        "-e", f"PGPASSWORD={inst['password']}",
        image,
        "psql",
        "-h", inst["host"],
        "-p", str(inst.get("port", 5432)),
        "-U", inst["user"],
        "-At",
        "-c", "SELECT datname FROM pg_database WHERE datistemplate = false;"
    ]

    result = subprocess.check_output(cmd, text=True)
    return result.splitlines()

def backup_mssql():
    if not config.get("mssql", {}).get("enabled"):
        return

    base = BACKUP_ROOT / "mssql"
    ensure_dir(base)

    for inst in config["mssql"]["instances"]:
        inst_dir = base / inst["name"]
        ensure_dir(inst_dir)

        ts_dir = inst_dir / TIMESTAMP
        ensure_dir(ts_dir)

        image = inst.get("image", "mcr.microsoft.com/mssql-tools")

        databases = inst.get("databases") or get_mssql_databases(inst, image)

        for db in databases:
            outfile = ts_dir / f"{db}.bak"

            print(f"Backing up MSSQL [{inst['name']}]: {db}")

            # Run BACKUP DATABASE
            backup_cmd = [
                "docker", "run", "--rm",
                "-v", f"{ts_dir}:/backup",
                image,
                "sqlcmd",
                "-S", f"{inst['host']},{inst.get('port', 1433)}",
                "-U", inst["user"],
                "-P", inst["password"],
                "-Q", f"""
BACKUP DATABASE [{db}]
TO DISK = '{outfile}'
WITH INIT
"""
            ]

            subprocess.run(
                backup_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )

        rotate_folders(inst_dir)

def get_mssql_databases(inst, image):
    cmd = [
        "docker", "run", "--rm",
        image,
        "sqlcmd",
        "-S", f"{inst['host']},{inst.get('port', 1433)}",
        "-U", inst["user"],
        "-P", inst["password"],
        "-Q", "SET NOCOUNT ON; SELECT name FROM sys.databases WHERE database_id > 4"
    ]

    result = subprocess.check_output(cmd).decode()
    return [line.strip() for line in result.splitlines() if line.strip()]

if __name__ == "__main__":
    backup_sqlite()
    backup_mysql()
    backup_postgresql()
    backup_mssql()
    print("All database backups completed successfully")
