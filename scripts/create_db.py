"""Create the MySQL database named in your .env (safe to run more than once).

Usage (from the SE_Project folder, with the venv active):
    python scripts/create_db.py
"""

import os
import sys

import pymysql
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

load_dotenv()


def main():
    """Read DATABASE_URL from .env and create that database if it is missing."""
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        sys.exit("No DATABASE_URL found. Did you create .env from .env.example?")

    url = make_url(raw_url)
    if not url.drivername.startswith("mysql"):
        sys.exit(f"DATABASE_URL is not a MySQL URL: {url.drivername}")

    try:
        connection = pymysql.connect(
            host=url.host or "localhost",
            port=url.port or 3306,
            user=url.username,
            password=url.password or "",
        )
    except pymysql.err.OperationalError as error:
        sys.exit(
            "Could not log in to MySQL. Check the user/password in .env.\n"
            "If your password has @ : / # or %, write @ as %40, : as %3A, / as %2F, "
            "# as %23, % as %25 (see README).\n"
            f"Details: {error}"
        )

    with connection:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{url.database}`")
    print(f"Database '{url.database}' is ready.")


if __name__ == "__main__":
    main()
