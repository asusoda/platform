"""Copy the platform database from SQLite to Postgres, then verify the copy.

Usage:
    DATABASE_URL=postgresql://... uv run alembic upgrade head          # create the schema first
    uv run python deploy/copy_sqlite_to_postgres.py sqlite:///./data/user.db postgresql://...
    uv run python deploy/copy_sqlite_to_postgres.py --verify-only sqlite:///./data/user.db postgresql://...

Stop the api and bot services before copying so nothing writes to SQLite during the copy. The
script refuses to copy into tables that already hold rows. Verification compares the row count of
every table and the points total of every organization; it exits non-zero on any difference.
The SQLite file is not modified, so switching DATABASE_URL back is the rollback.
"""

import argparse
import sys

from sqlalchemy import MetaData, create_engine, func, inspect, select, text

SKIPPED_TABLES = {"alembic_version"}
BATCH_SIZE = 1000


def counts(engine, tables) -> dict[str, int]:
    with engine.connect() as conn:
        return {t.name: conn.execute(select(func.count()).select_from(t)).scalar_one() for t in tables}


def points_by_org(engine, metadata) -> dict:
    if "points" not in metadata.tables:
        return {}
    points = metadata.tables["points"]
    with engine.connect() as conn:
        rows = conn.execute(
            select(points.c.organization_id, func.coalesce(func.sum(points.c.points), 0)).group_by(
                points.c.organization_id
            )
        )
        return {org_id: float(total) for org_id, total in rows}


def copy(source, target, source_meta, target_meta) -> None:
    for target_table in target_meta.sorted_tables:
        name = target_table.name
        if name in SKIPPED_TABLES or name not in source_meta.tables:
            continue
        source_table = source_meta.tables[name]
        columns = [c.name for c in target_table.columns if c.name in source_table.c]
        with source.connect() as src, target.begin() as dst:
            if dst.execute(select(func.count()).select_from(target_table)).scalar_one():
                raise SystemExit(f"Target table {name} already has rows; copy into an empty database")
            result = src.execute(select(*[source_table.c[c] for c in columns]))
            copied = 0
            while batch := result.fetchmany(BATCH_SIZE):
                dst.execute(target_table.insert(), [dict(zip(columns, row, strict=True)) for row in batch])
                copied += len(batch)
        print(f"copied {name}: {copied}")

    # Move each serial id sequence past the copied ids
    with target.begin() as dst:
        for table in target_meta.sorted_tables:
            if "id" not in table.c or table.name in SKIPPED_TABLES:
                continue
            dst.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "  # nosec B608 - table names come from the schema
                    f"COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"
                )
            )


def verify(source, target, source_meta, target_meta) -> bool:
    tables = [t for t in source_meta.sorted_tables if t.name not in SKIPPED_TABLES]
    source_counts = counts(source, tables)
    target_counts = counts(target, [target_meta.tables[t.name] for t in tables if t.name in target_meta.tables])
    ok = True
    for name, expected in source_counts.items():
        actual = target_counts.get(name)
        status = "ok" if actual == expected else "MISMATCH"
        ok = ok and actual == expected
        print(f"{status:8} {name}: sqlite={expected} postgres={actual}")
    source_points, target_points = points_by_org(source, source_meta), points_by_org(target, target_meta)
    for org_id in sorted(set(source_points) | set(target_points), key=str):
        expected, actual = source_points.get(org_id), target_points.get(org_id)
        status = "ok" if expected == actual else "MISMATCH"
        ok = ok and expected == actual
        print(f"{status:8} points total for org {org_id}: sqlite={expected} postgres={actual}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="SQLite URL, e.g. sqlite:///./data/user.db")
    parser.add_argument("target", help="Postgres URL, migrated to head")
    parser.add_argument("--verify-only", action="store_true", help="compare without copying")
    args = parser.parse_args()

    source, target = create_engine(args.source), create_engine(args.target)
    if not inspect(target).has_table("alembic_version"):
        print("Target has no schema. Run DATABASE_URL=<target> uv run alembic upgrade head first.")
        return 2
    source_meta, target_meta = MetaData(), MetaData()
    source_meta.reflect(bind=source)
    target_meta.reflect(bind=target)

    if not args.verify_only:
        copy(source, target, source_meta, target_meta)
    if verify(source, target, source_meta, target_meta):
        print("Verified: every table and every org's points total match.")
        return 0
    print("Verification failed. Keep DATABASE_URL on SQLite.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
