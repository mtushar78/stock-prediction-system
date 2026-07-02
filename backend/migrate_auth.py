"""
One-off migration: add multi-user auth to the DSE Sniper database.

Idempotent — safe to run repeatedly. It will:
  1. Create the ``users`` table.
  2. Seed the owner account (mtushar78@gmail.com / Tushar@12) if missing.
  3. Add ``user_id`` to ``portfolio`` (rebuilt with composite PK (user_id, ticker))
     and to ``purchase_history``.
  4. Assign any pre-existing (owner-less) portfolio / purchase_history rows to
     the seeded owner so nothing is lost.

Run once after deploying the auth changes:
    python backend/migrate_auth.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db_manager import DatabaseManager
from src import auth

OWNER_EMAIL = "mtushar78@gmail.com"
OWNER_PASSWORD = "Tushar@12"


def _columns(cur, table: str):
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def _table_exists(cur, table: str) -> bool:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def main():
    # 1 + 2: users table + seed owner
    auth.ensure_users_table()
    owner = auth.get_user_by_email(OWNER_EMAIL)
    if owner:
        print(f"[ok] Owner user already exists: {OWNER_EMAIL} (id={owner['id']})")
    else:
        owner = auth.create_user(OWNER_EMAIL, OWNER_PASSWORD)
        print(f"[ok] Created owner user: {OWNER_EMAIL} (id={owner['id']})")
    owner_id = owner["id"]

    db = DatabaseManager()
    conn = db.engine.raw_connection()
    try:
        cur = conn.cursor()

        # 3a: portfolio — rebuild with (user_id, ticker) composite PK.
        if _table_exists(cur, "portfolio"):
            cols = _columns(cur, "portfolio")
            if "user_id" not in cols:
                print("- Rebuilding portfolio with user_id ...")
                cur.execute(
                    """
                    CREATE TABLE portfolio_new (
                        user_id INTEGER NOT NULL,
                        ticker TEXT NOT NULL,
                        buy_price REAL NOT NULL,
                        quantity INTEGER NOT NULL,
                        highest_seen REAL NOT NULL,
                        purchase_date TEXT NOT NULL,
                        notes TEXT,
                        total_cost REAL DEFAULT 0,
                        commission_paid REAL DEFAULT 0,
                        PRIMARY KEY (user_id, ticker)
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO portfolio_new
                        (user_id, ticker, buy_price, quantity, highest_seen,
                         purchase_date, notes, total_cost, commission_paid)
                    SELECT ?, ticker, buy_price, quantity, highest_seen,
                           purchase_date, notes,
                           COALESCE(total_cost, 0), COALESCE(commission_paid, 0)
                    FROM portfolio
                    """,
                    (owner_id,),
                )
                moved = cur.rowcount
                cur.execute("DROP TABLE portfolio")
                cur.execute("ALTER TABLE portfolio_new RENAME TO portfolio")
                print(f"  -> migrated {moved} existing position(s) to owner")
            else:
                print("[ok] portfolio already has user_id")

        # 3b: purchase_history — add user_id column + backfill + index.
        if _table_exists(cur, "purchase_history"):
            cols = _columns(cur, "purchase_history")
            if "user_id" not in cols:
                print("- Adding user_id to purchase_history ...")
                cur.execute("ALTER TABLE purchase_history ADD COLUMN user_id INTEGER")
                cur.execute(
                    "UPDATE purchase_history SET user_id = ? WHERE user_id IS NULL",
                    (owner_id,),
                )
                print(f"  -> backfilled {cur.rowcount} history row(s) to owner")
            else:
                print("[ok] purchase_history already has user_id")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_purchase_history_user "
                "ON purchase_history(user_id, ticker)"
            )

        conn.commit()
        print("\n[DONE] Auth migration complete.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
