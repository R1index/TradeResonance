from __future__ import annotations

import asyncio
import csv
import io
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

import discord
from discord.ext import commands

APP_TITLE = "Trade Resonance Bot"
DB_PATH = os.environ.get("APP_DB", "data.sqlite")
BOT_PREFIX = os.environ.get("BOT_PREFIX", "!")
DEFAULT_LIMIT = 10

TREND_MAP = {
    "up": "📈 rising",
    "down": "📉 falling",
    "flat": "⏸️ unchanged",
}


# ---------------------- DB helpers ----------------------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    product TEXT NOT NULL,
    price REAL NOT NULL CHECK(price >= 0),
    trend TEXT CHECK(trend IN ('up','down','flat')),
    percent REAL,
    is_production_city INTEGER NOT NULL DEFAULT 0 CHECK(is_production_city IN (0,1)),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_city_product ON entries(city, product);
CREATE INDEX IF NOT EXISTS idx_entries_created ON entries(created_at);
"""


def ensure_schema() -> None:
    with get_conn() as c:
        c.executescript(SCHEMA_SQL)
        cols = {row[1] for row in c.execute("PRAGMA table_info(entries)")}
        if "is_production_city" not in cols:
            c.execute(
                "ALTER TABLE entries ADD COLUMN is_production_city INTEGER NOT NULL DEFAULT 0"
            )


# ---------------------- Queries & logic ----------------------

def insert_entry(
    city: str,
    product: str,
    price: float,
    trend: str = "flat",
    percent: Optional[float] = None,
    is_production_city: bool = False,
) -> Dict[str, Any]:
    city = city.strip()
    product = product.strip()
    if not city or not product:
        raise ValueError("City and product are required.")
    if price < 0:
        raise ValueError("Price must be non-negative.")
    trend = (trend or "flat").lower()
    if trend not in ("up", "down", "flat"):
        trend = "flat"

    created_at = datetime.utcnow().isoformat()
    with get_conn() as c:
        c.execute(
            "INSERT INTO entries(city, product, price, trend, percent, is_production_city, created_at) VALUES (?,?,?,?,?,?,?)",
            (city, product, price, trend, percent, 1 if is_production_city else 0, created_at),
        )
    return {
        "city": city,
        "product": product,
        "price": price,
        "trend": trend,
        "percent": percent,
        "is_production_city": bool(is_production_city),
        "created_at": created_at,
    }


def latest_prices(limit: int = DEFAULT_LIMIT) -> List[sqlite3.Row]:
    sql = """
    WITH latest AS (
      SELECT e.*
      FROM entries e
      JOIN (
        SELECT city, product, MAX(datetime(created_at)) AS mx
        FROM entries
        GROUP BY city, product
      ) m
      ON e.city = m.city AND e.product = m.product AND datetime(e.created_at) = m.mx
    )
    SELECT * FROM latest ORDER BY datetime(created_at) DESC LIMIT ?
    """
    with get_conn() as c:
        return c.execute(sql, (limit,)).fetchall()


def compute_routes(limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
    sql = """
    WITH latest AS (
      SELECT e.*
      FROM entries e
      JOIN (
        SELECT city, product, MAX(datetime(created_at)) AS mx
        FROM entries
        GROUP BY city, product
      ) m
      ON e.city = m.city AND e.product = m.product AND datetime(e.created_at) = m.mx
    )
    SELECT
      a.product AS product,
      a.city AS from_city,
      b.city AS to_city,
      a.price AS from_price,
      b.price AS to_price,
      (b.price - a.price) AS profit_abs,
      CASE WHEN a.price > 0 THEN (b.price - a.price) * 100.0 / a.price ELSE NULL END AS profit_pct
    FROM latest a
    JOIN latest b
      ON a.product = b.product AND a.city <> b.city
    WHERE b.price > a.price AND a.is_production_city = 1
    ORDER BY profit_pct DESC, profit_abs DESC
    LIMIT ?
    """
    with get_conn() as c:
        rows = c.execute(sql, (limit,)).fetchall()
        return [dict(row) for row in rows]


def product_latest_prices(product: str, sort: str = "asc") -> List[sqlite3.Row]:
    order = "DESC" if sort == "desc" else "ASC"
    sql = f"""
    WITH latest AS (
      SELECT e.*
      FROM entries e
      JOIN (
        SELECT city, MAX(datetime(created_at)) AS mx
        FROM entries
        WHERE product = ?
        GROUP BY city
      ) m
      ON e.city = m.city AND datetime(e.created_at) = m.mx
      WHERE e.product = ?
    )
    SELECT * FROM latest ORDER BY price {order}, datetime(created_at) DESC
    """
    with get_conn() as c:
        return c.execute(sql, (product, product)).fetchall()


def series(city: str, product: str) -> List[sqlite3.Row]:
    sql = (
        "SELECT created_at AS ts, price, trend, percent FROM entries "
        "WHERE city=? AND product=? ORDER BY datetime(created_at) ASC"
    )
    with get_conn() as c:
        return c.execute(sql, (city, product)).fetchall()


def suggest_values(field: str, query: str | None = None, limit: int = 20) -> List[str]:
    if field not in ("city", "product"):
        raise ValueError("Field must be either city or product.")
    sql = f"SELECT DISTINCT {field} FROM entries"
    params: Sequence[Any]
    if query:
        sql += f" WHERE LOWER({field}) LIKE ?"
        params = (f"%{query.lower()}%",)
    else:
        params = ()
    sql += f" ORDER BY {field} ASC LIMIT {limit}"
    with get_conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [row[0] for row in rows]


def export_csv_bytes() -> bytes:
    sql = "SELECT * FROM entries ORDER BY datetime(created_at) DESC"
    with get_conn() as c:
        rows = c.execute(sql).fetchall()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "created_at",
            "city",
            "product",
            "price",
            "trend",
            "percent",
            "is_production_city",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r["id"],
                r["created_at"],
                r["city"],
                r["product"],
                r["price"],
                r["trend"],
                "" if r["percent"] is None else r["percent"],
                r["is_production_city"],
            ]
        )
    return buffer.getvalue().encode("utf-8")


def import_from_csv_bytes(data: bytes) -> int:
    if not data:
        return 0
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return 0

    def norm(key: Optional[str]) -> str:
        return (key or "").strip().lower()

    now = datetime.utcnow().isoformat()
    payload: List[tuple[Any, ...]] = []
    for row in reader:
        lowered = {norm(k): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        city = (lowered.get("city") or "").strip()
        product_val = (lowered.get("product") or "").strip()
        price_raw = (lowered.get("price") or "").replace(",", ".").strip()
        trend = (lowered.get("trend") or "flat").strip().lower()
        percent_raw = (lowered.get("percent") or "").replace(",", ".").strip()
        is_prod_raw = (lowered.get("is_production_city") or "").strip().lower()
        created_raw = (lowered.get("created_at") or "").strip()

        if not city or not product_val or not price_raw:
            continue

        try:
            price = float(price_raw)
        except ValueError:
            continue

        percent = None
        if percent_raw:
            try:
                percent = float(percent_raw)
            except ValueError:
                percent = None

        if trend not in ("up", "down", "flat"):
            trend = "flat"

        if is_prod_raw in ("1", "true", "yes", "y", "production", "prod"):
            is_prod = 1
        else:
            try:
                is_prod = 1 if int(is_prod_raw) != 0 else 0
            except ValueError:
                is_prod = 0

        created_at = created_raw or now
        if created_raw:
            try:
                datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            except ValueError:
                try:
                    parsed = datetime.strptime(created_raw, "%Y-%m-%d %H:%M:%S")
                    created_at = parsed.isoformat()
                except ValueError:
                    created_at = now

        payload.append((city, product_val, price, trend, percent, is_prod, created_at))

    if not payload:
        return 0

    with get_conn() as c:
        c.executemany(
            "INSERT INTO entries(city, product, price, trend, percent, is_production_city, created_at) VALUES (?,?,?,?,?,?,?)",
            payload,
        )
    return len(payload)


# ---------------------- Discord helpers ----------------------

def format_rows(title: str, headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    lines = [title, ""]
    header_line = " | ".join(headers)
    lines.append(header_line)
    lines.append("-" * len(header_line))
    for row in rows:
        lines.append(" | ".join(row))
    if len(lines) == 4:
        lines.append("(no data)")
    return "```\n" + "\n".join(lines) + "\n```"


def human_percent(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.0f}%"


async def run_db(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


def parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    value = value.strip().lower()
    return value in {"1", "true", "yes", "y", "production", "prod", "on"}


# ---------------------- Discord bot ----------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, description=APP_TITLE)


@bot.event
async def on_ready():
    ensure_schema()
    print(f"Logged in as {bot.user} (id={bot.user.id})")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.BadArgument):
        await ctx.reply(f"Argument error: {error}")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("Not enough arguments. Type !help for usage details.")
    else:
        await ctx.reply(f"An error occurred: {error}")
        raise error


@bot.command(name="help")
async def help_command(ctx: commands.Context):
    help_text = (
        "**Trade Resonance Bot**\n"
        "Available commands:\n"
        "`!add <city> <product> <price> [trend] [percent] [production]` — add a new entry.\n"
        "`!latest [limit]` — show the latest prices per city.\n"
        "`!routes [limit]` — show the most profitable trade routes.\n"
        "`!product <product> [asc|desc]` — list prices for a specific product.\n"
        "`!series <city> <product>` — display the price history for a pair.\n"
        "`!suggest <city|product> [query]` — provide autocomplete suggestions.\n"
        "`!export` — export all records to CSV.\n"
        "`!import` (with a CSV attachment) — import records.\n"
    )
    await ctx.reply(help_text)


@bot.command(name="add")
async def add_entry_command(
    ctx: commands.Context,
    city: str,
    product: str,
    price: float,
    trend: str = "flat",
    percent: Optional[str] = None,
    production: Optional[str] = None,
):
    try:
        percent_value = float(percent.replace(",", ".")) if percent else None
    except ValueError:
        await ctx.reply("Could not parse percent, please provide a number.")
        return

    try:
        entry = await run_db(
            insert_entry,
            city,
            product,
            price,
            trend,
            percent_value,
            parse_bool(production),
        )
    except ValueError as exc:
        await ctx.reply(str(exc))
        return

    trend_label = TREND_MAP.get(entry["trend"], entry["trend"])
    percent_label = human_percent(entry["percent"])
    message = (
        "Entry added:\n"
        f"City: **{entry['city']}**, product: **{entry['product']}**\n"
        f"Price: {entry['price']:.0f}, trend: {trend_label}, percent: {percent_label}\n"
        f"Production city: {'yes' if entry['is_production_city'] else 'no'}"
    )
    await ctx.reply(message)


@bot.command(name="latest")
async def latest_command(ctx: commands.Context, limit: Optional[int] = None):
    limit = limit or DEFAULT_LIMIT
    limit = max(1, min(limit, 50))
    rows = await run_db(latest_prices, limit)
    table = format_rows(
        "Latest entries",
        ["City", "Prod", "Price", "Trend", "%", "When"],
        [
            [
                row["city"],
                "✓" if row["is_production_city"] else "—",
                f"{row['price']:.0f}",
                TREND_MAP.get(row["trend"], row["trend"]),
                human_percent(row["percent"]),
                row["created_at"][:19].replace("T", " "),
            ]
            for row in rows
        ],
    )
    await ctx.reply(table)


@bot.command(name="routes")
async def routes_command(ctx: commands.Context, limit: Optional[int] = None):
    limit = limit or DEFAULT_LIMIT
    limit = max(1, min(limit, 50))
    routes = await run_db(compute_routes, limit)
    table = format_rows(
        "Top profit routes",
        ["Product", "From", "To", "Price from", "Price to", "Profit", "%"],
        [
            [
                r["product"],
                r["from_city"],
                r["to_city"],
                f"{r['from_price']:.0f}",
                f"{r['to_price']:.0f}",
                f"{r['profit_abs']:.0f}",
                human_percent(r["profit_pct"]),
            ]
            for r in routes
        ],
    )
    await ctx.reply(table)


@bot.command(name="product")
async def product_command(ctx: commands.Context, product: str, sort: str = "asc"):
    sort = sort.lower()
    if sort not in ("asc", "desc"):
        sort = "asc"
    rows = await run_db(product_latest_prices, product, sort)
    if not rows:
        await ctx.reply("No data for the selected product.")
        return
    table = format_rows(
        f"Prices for {product}",
        ["City", "Prod", "Price", "Trend", "%", "When"],
        [
            [
                row["city"],
                "✓" if row["is_production_city"] else "—",
                f"{row['price']:.0f}",
                TREND_MAP.get(row["trend"], row["trend"]),
                human_percent(row["percent"]),
                row["created_at"][:19].replace("T", " "),
            ]
            for row in rows
        ],
    )
    await ctx.reply(table)


@bot.command(name="series")
async def series_command(ctx: commands.Context, city: str, product: str):
    rows = await run_db(series, city, product)
    if not rows:
        await ctx.reply("No data for the selected city/product pair.")
        return
    table = format_rows(
        f"Price history for {city} / {product}",
        ["When", "Price", "Trend", "%"],
        [
            [
                row["ts"][:19].replace("T", " "),
                f"{row['price']:.0f}",
                TREND_MAP.get(row["trend"], row["trend"]),
                human_percent(row["percent"]),
            ]
            for row in rows
        ],
    )
    await ctx.reply(table)


@bot.command(name="suggest")
async def suggest_command(ctx: commands.Context, field: str, *, query: str = ""):
    field = field.lower()
    try:
        values = await run_db(suggest_values, field, query)
    except ValueError as exc:
        await ctx.reply(str(exc))
        return
    if not values:
        await ctx.reply("No matches found.")
        return
    message = "Suggestions:\n" + "\n".join(f"• {value}" for value in values)
    await ctx.reply(message)


@bot.command(name="export")
async def export_command(ctx: commands.Context):
    data = await run_db(export_csv_bytes)
    buffer = io.BytesIO(data)
    buffer.seek(0)
    await ctx.reply(file=discord.File(buffer, filename="entries.csv"))


@bot.command(name="import")
async def import_command(ctx: commands.Context):
    if not ctx.message.attachments:
        await ctx.reply("Attach a CSV file to the message.")
        return
    attachment = ctx.message.attachments[0]
    data = await attachment.read()
    count = await run_db(import_from_csv_bytes, data)
    await ctx.reply(f"Imported records: {count}")


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN environment variable is not set.")
    ensure_schema()
    bot.run(token)


if __name__ == "__main__":
    main()
