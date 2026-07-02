"""
Create a login user (closed system — no public registration).

Usage:
    python backend/create_user.py <email> <password>
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src import auth


def main():
    if len(sys.argv) != 3:
        print("Usage: python backend/create_user.py <email> <password>")
        sys.exit(1)
    email, password = sys.argv[1], sys.argv[2]
    try:
        user = auth.create_user(email, password)
        print(f"[ok] Created user {user['email']} (id={user['id']})")
    except ValueError as e:
        print(f"[error] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
