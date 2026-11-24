"""Reusable pyodbc connection helper for SQL Server."""
import os
from pathlib import Path
from dotenv import load_dotenv
import pyodbc

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

def build_connection_string(database=None):
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    server = os.getenv("DB_SERVER", "localhost")
    port = os.getenv("DB_PORT", "1433")
    db = database or os.getenv("DB_NAME", "tennis_db")
    trust = os.getenv("DB_TRUST_CERT", "yes").lower()
    integrated = os.getenv("DB_INTEGRATED_SECURITY", "no").lower() in {"1","yes","true","y"}
    parts = [
        f"DRIVER={{{driver}}}", f"SERVER={server},{port}", f"DATABASE={db}",
        "Encrypt=yes", f"TrustServerCertificate={'yes' if trust in {'1','yes','true','y'} else 'no'}"
    ]
    if integrated:
        parts.append("Trusted_Connection=yes")
    else:
        user, password = os.getenv("DB_USER"), os.getenv("DB_PASSWORD")
        if not user or password is None:
            raise RuntimeError("Set DB_USER and DB_PASSWORD, or DB_INTEGRATED_SECURITY=yes, in .env")
        parts += [f"UID={user}", f"PWD={password}"]
    return ";".join(parts) + ";"

def get_connection(database=None, autocommit=False):
    """Return a new connection; the caller must close it."""
    return pyodbc.connect(build_connection_string(database), autocommit=autocommit)
