from pathlib import Path


APP_TABLES = {
    "clients",
    "invoices",
    "vendors",
    "processing_logs",
    "client_configs",
}


def _migration_sql() -> str:
    migrations_dir = Path(__file__).parents[3] / "supabase" / "migrations"
    return "\n".join(path.read_text() for path in sorted(migrations_dir.glob("*.sql"))).lower()


def test_app_tables_enable_row_level_security():
    sql = _migration_sql()

    for table in APP_TABLES:
        assert f"alter table if exists public.{table} enable row level security" in sql or (
            f"alter table public.{table} enable row level security" in sql
        )


def test_app_tables_revoke_browser_role_table_access():
    sql = _migration_sql()

    for table in APP_TABLES:
        assert f"revoke all on table public.{table} from anon, authenticated, public" in sql
