#!/usr/bin/env python
"""
Migration Utility: SQLite to PostgreSQL for VideoVlog-ML Social Media Application

Usage:
    python migrate_sqlite_to_postgres.py [--help]
    python migrate_sqlite_to_postgres.py --export-only
    python migrate_sqlite_to_postgres.py --import-only

This script performs the following operations:
1. Validates PostgreSQL connection settings from .env (or CLI arguments)
2. Ensures target PostgreSQL database exists (creates it if needed)
3. Dumps app data from SQLite (excluding contenttypes and auth.permission)
4. Applies Django migrations to PostgreSQL
5. Loads data fixture into PostgreSQL
6. Resets PostgreSQL primary key sequences for seamless future inserts
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

def run_command(cmd, env=None, check=True):
    """Run a shell command and print output."""
    full_env = os.environ.copy()
    full_env["PYTHONIOENCODING"] = "utf-8"
    full_env["PYTHONUTF8"] = "1"
    if env:
        full_env.update(env)
    print(f"\n[RUNNING] {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(BASE_DIR), env=full_env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.stdout:
        print(res.stdout.strip())
    if res.stderr and res.returncode != 0:
        print(f"[ERROR] {res.stderr.strip()}")
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed with return code {res.returncode}")
    return res

def test_and_create_pg_database(db_name, db_user, db_password, db_host, db_port):
    """Ensure PostgreSQL database exists, creating it if needed."""
    try:
        import psycopg
        from psycopg import sql
    except ImportError:
        print("[!] psycopg is not installed. Run: pip install \"psycopg[binary]\"")
        sys.exit(1)

    print(f"\n[1/5] Checking connection to PostgreSQL server ({db_host}:{db_port}) as user '{db_user}'...")
    try:
        conn = psycopg.connect(
            dbname="postgres",
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            autocommit=True
        )
    except Exception as e:
        print(f"\n[!] Failed to connect to PostgreSQL server: {e}")
        print("\nPlease verify the credentials in your .env file or command line arguments:")
        print(f"  DB_NAME={db_name}")
        print(f"  DB_USER={db_user}")
        print(f"  DB_PASSWORD={'*****' if db_password else '(EMPTY - please set your password)'}")
        print(f"  DB_HOST={db_host}")
        print(f"  DB_PORT={db_port}\n")
        sys.exit(1)

    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
        exists = cur.fetchone()
        if not exists:
            print(f"[*] Database '{db_name}' does not exist. Creating it now...")
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            print(f"[OK] Database '{db_name}' created successfully.")
        else:
            print(f"[OK] Database '{db_name}' already exists.")
    conn.close()

def export_sqlite_data(dump_path):
    """Export application data from SQLite to a JSON fixture."""
    print(f"\n[2/5] Exporting SQLite data to {dump_path.name}...")
    sqlite_env = {
        "DB_ENGINE": "django.db.backends.sqlite3",
        "DB_NAME": "db.sqlite3"
    }
    
    cmd = [
        sys.executable, "manage.py", "dumpdata",
        "--natural-foreign",
        "--natural-primary",
        "--exclude", "contenttypes",
        "--exclude", "auth.permission",
        "--indent", "2",
        "--output", str(dump_path)
    ]
    run_command(cmd, env=sqlite_env)
    print(f"[OK] Data exported successfully to {dump_path}")

def run_pg_migrations(pg_env=None):
    """Apply Django migrations to PostgreSQL."""
    print("\n[3/5] Applying Django migrations to PostgreSQL database...")
    run_command([sys.executable, "manage.py", "migrate"], env=pg_env)
    print("[OK] PostgreSQL migrations completed.")

def import_pg_data(dump_path, pg_env=None):
    """Load JSON fixture into PostgreSQL."""
    print(f"\n[4/5] Loading data from {dump_path.name} into PostgreSQL...")
    run_command([sys.executable, "manage.py", "loaddata", str(dump_path)], env=pg_env)
    print("[OK] Data loaded successfully.")

def reset_pg_sequences(pg_env=None):
    """Reset PostgreSQL primary key sequences so subsequent inserts work properly."""
    print("\n[5/5] Resetting PostgreSQL primary key sequences...")
    res = run_command([sys.executable, "manage.py", "sqlsequencereset", "accounts", "post", "admin", "auth"], env=pg_env, check=False)
    if res.returncode == 0 and res.stdout.strip():
        sql_lines = res.stdout.strip()
        # Execute generated SQL using psycopg directly or django connection
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'social_media.settings')
        if pg_env:
            for k, v in pg_env.items():
                os.environ[k] = v
        django.setup()
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(sql_lines)
        print("[OK] Primary key sequences reset successfully.")
    else:
        print("[!] Sequence reset SQL generated was empty or skipped.")

def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument("--export-only", action="store_true", help="Only export SQLite data to JSON")
    parser.add_argument("--import-only", action="store_true", help="Only import existing JSON dump to PostgreSQL")
    parser.add_argument("--dump-file", default="sqlite_dump.json", help="Dump file path (default: sqlite_dump.json)")
    parser.add_argument("--db-name", default=None, help="PostgreSQL database name")
    parser.add_argument("--db-user", default=None, help="PostgreSQL user")
    parser.add_argument("--db-password", default=None, help="PostgreSQL password")
    parser.add_argument("--db-host", default=None, help="PostgreSQL host")
    parser.add_argument("--db-port", default=None, help="PostgreSQL port")
    args = parser.parse_args()

    dump_path = BASE_DIR / args.dump_file

    db_name = args.db_name or os.environ.get("DB_NAME", "videovlog_db")
    db_user = args.db_user or os.environ.get("DB_USER", "postgres")
    db_password = args.db_password if args.db_password is not None else os.environ.get("DB_PASSWORD", "")
    db_host = args.db_host or os.environ.get("DB_HOST", "localhost")
    db_port = args.db_port or os.environ.get("DB_PORT", "5432")

    pg_env = {
        "DB_ENGINE": "django.db.backends.postgresql",
        "DB_NAME": db_name,
        "DB_USER": db_user,
        "DB_PASSWORD": db_password,
        "DB_HOST": db_host,
        "DB_PORT": db_port
    }

    if args.export_only:
        export_sqlite_data(dump_path)
        print("\n[OK] Export finished successfully.")
        return

    if args.import_only:
        test_and_create_pg_database(db_name, db_user, db_password, db_host, db_port)
        run_pg_migrations(pg_env)
        import_pg_data(dump_path, pg_env)
        reset_pg_sequences(pg_env)
        print("\n[OK] Import finished successfully.")
        return

    # Full migration flow
    export_sqlite_data(dump_path)
    test_and_create_pg_database(db_name, db_user, db_password, db_host, db_port)
    run_pg_migrations(pg_env)
    import_pg_data(dump_path, pg_env)
    reset_pg_sequences(pg_env)

    print("\n" + "=" * 50)
    print("  MIGRATION TO POSTGRESQL COMPLETED SUCCESSFULLY!")
    print("=" * 50)
    print(f"PostgreSQL Database : {db_name}")
    print(f"Host                : {db_host}:{db_port}")
    print(f"User                : {db_user}")
    print("\nYou can now run your server with:")
    print("  python manage.py runserver")
    print("=" * 50)

if __name__ == "__main__":
    main()
