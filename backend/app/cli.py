"""Operator commands.

Run inside the API container so the environment matches the app:

    python -m app.cli make-admin you@example.com
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select

from .database import SessionLocal
from .models import Membership, User, Workspace


def make_admin(email: str, workspace_slug: str = "", role: str = "owner") -> int:
    email = email.strip().lower()
    if not email:
        print("An email address is required.", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if not user:
            print(
                f"No account for {email}. Register it first, then run this command.",
                file=sys.stderr,
            )
            return 1

        query = (
            select(Membership, Workspace)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .where(Membership.user_id == user.id)
        )
        if workspace_slug:
            query = query.where(Workspace.slug == workspace_slug.strip().lower())
        rows = db.execute(query).all()
        if not rows:
            print(
                "This account is not a member of any workspace"
                + (f" with slug {workspace_slug}." if workspace_slug else "."),
                file=sys.stderr,
            )
            return 1

        for membership, workspace in rows:
            membership.role = role
            print(f"{email} is now {role} of {workspace.name} ({workspace.slug}).")
        db.commit()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    admin = subparsers.add_parser(
        "make-admin",
        help="Grant an existing account full admin access to its workspaces.",
    )
    admin.add_argument("email", help="Email address of the account to promote.")
    admin.add_argument(
        "--workspace",
        default="",
        help="Limit the change to one workspace slug.",
    )
    admin.add_argument(
        "--role",
        choices=("owner", "admin"),
        default="owner",
        help="Role to assign. Owner is the highest role (default).",
    )

    args = parser.parse_args(argv)
    if args.command == "make-admin":
        return make_admin(args.email, args.workspace, args.role)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
