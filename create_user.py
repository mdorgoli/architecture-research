import argparse
import getpass
import re

from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models import User


def main():
    parser = argparse.ArgumentParser(description="Create a local user with an Argon2 password hash.")
    parser.add_argument("username")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,64}", args.username):
        parser.error("Username must contain 3-64 ASCII letters, digits, _, . or -.")
    password = getpass.getpass("Password (12-128 characters): ")
    if not 12 <= len(password) <= 128:
        parser.error("Password must contain 12-128 characters.")
    if password != getpass.getpass("Repeat password: "):
        parser.error("Passwords do not match.")
    with SessionLocal() as db:
        db.add(User(username=args.username, password_hash=PasswordHash.recommended().hash(password)))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            parser.error("Username already exists.")
    print("User created.")


if __name__ == "__main__":
    main()
