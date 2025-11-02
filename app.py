from __future__ import annotations

import asyncio
import csv
import io
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Union, Literal

import discord
from discord.ext import commands

APP_TITLE = "Trade Resonance Bot"
DB_PATH = os.environ.get("APP_DB", "data.sqlite")
BOT_PREFIX = os.environ.get("BOT_PREFIX", "!")
DEFAULT_LIMIT = 10
EMBED_COLOR_PRIMARY = discord.Color.blurple()

TREND_MAP = {
    "up": "📈 rising",
    "down": "📉 falling",
    "flat": "⏸️ unchanged",
}

TrendLiteral = Literal["up", "down", "flat"]
SortLiteral = Literal["asc", "desc"]
SuggestFieldLiteral = Literal["city", "product"]


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

def human_percent(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.0f}%"


def human_timestamp(value: Optional[str]) -> str:
    if not value:
        return "—"
    return value[:19].replace("T", " ")


def format_trend_label(trend: Optional[str], percent: Optional[float]) -> str:
    label = TREND_MAP.get((trend or "").lower(), trend or "—")
    percent_label = human_percent(percent)
    if percent_label == "—":
        return label
    return f"{label} ({percent_label})"


def build_entry_confirmation_embed(entry: Dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        title="Entry saved",
        description=f"Product **{entry['product']}** in **{entry['city']}**",
        color=discord.Color.green(),
    )
    embed.add_field(name="Price", value=f"{entry['price']:.0f}", inline=True)
    embed.add_field(
        name="Trend",
        value=format_trend_label(entry["trend"], entry.get("percent")),
        inline=True,
    )
    embed.add_field(
        name="Production city",
        value="Yes" if entry.get("is_production_city") else "No",
        inline=True,
    )
    embed.set_footer(text=f"Recorded at {human_timestamp(entry.get('created_at'))} UTC")
    return embed


def build_latest_embed(rows: Sequence[sqlite3.Row]) -> discord.Embed:
    embed = discord.Embed(title="Latest entries", color=EMBED_COLOR_PRIMARY)
    if not rows:
        embed.description = "No data yet. Use the button below to add an entry."
        return embed
    for idx, row in enumerate(rows, start=1):
        name = f"{idx}. {row['product']} — {row['city']}"
        value = (
            f"Price: **{row['price']:.0f}**\n"
            f"Trend: {format_trend_label(row['trend'], row['percent'])}\n"
            f"Production: {'Yes' if row['is_production_city'] else 'No'}\n"
            f"Updated: {human_timestamp(row['created_at'])}"
        )
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=f"Showing {len(rows)} recent entries")
    return embed


def build_routes_embed(routes: Sequence[Dict[str, Any]]) -> discord.Embed:
    embed = discord.Embed(title="Top profit routes", color=EMBED_COLOR_PRIMARY)
    if not routes:
        embed.description = "No profitable routes found yet."
        return embed
    for idx, route in enumerate(routes, start=1):
        name = f"{idx}. {route['product']}"
        value = (
            f"From: **{route['from_city']}** ({route['from_price']:.0f})\n"
            f"To: **{route['to_city']}** ({route['to_price']:.0f})\n"
            f"Profit: **{route['profit_abs']:.0f}** ({human_percent(route['profit_pct'])})"
        )
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=f"Showing top {len(routes)} routes")
    return embed


def build_product_embed(product: str, rows: Sequence[sqlite3.Row]) -> discord.Embed:
    embed = discord.Embed(
        title=f"Prices for {product}",
        color=EMBED_COLOR_PRIMARY,
    )
    if not rows:
        embed.description = "No data for the selected product."
        return embed
    for row in rows:
        name = f"{row['city']}"
        value = (
            f"Price: **{row['price']:.0f}**\n"
            f"Trend: {format_trend_label(row['trend'], row['percent'])}\n"
            f"Production: {'Yes' if row['is_production_city'] else 'No'}\n"
            f"Updated: {human_timestamp(row['created_at'])}"
        )
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=f"Sorted by price {'ascending' if rows and rows[0]['price'] <= rows[-1]['price'] else 'descending'}")
    return embed


def build_series_embed(city: str, product: str, rows: Sequence[sqlite3.Row]) -> discord.Embed:
    embed = discord.Embed(
        title=f"Price history for {city} / {product}",
        color=EMBED_COLOR_PRIMARY,
    )
    if not rows:
        embed.description = "No data for the selected city/product pair."
        return embed
    lines = [
        f"**{human_timestamp(row['ts'])}** — {row['price']:.0f} ({format_trend_label(row['trend'], row['percent'])})"
        for row in rows
    ]
    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Total points: {len(rows)}")
    return embed


def build_suggest_embed(field: str, values: Sequence[str]) -> discord.Embed:
    embed = discord.Embed(
        title=f"Suggestions for {field}",
        color=EMBED_COLOR_PRIMARY,
    )
    if not values:
        embed.description = "No matches found."
        return embed
    embed.description = "\n".join(f"• {value}" for value in values)
    embed.set_footer(text=f"Total suggestions: {len(values)}")
    return embed


async def run_db(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


def parse_bool(value: Optional[Union[str, bool]]) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    value = value.strip().lower()
    return value in {"1", "true", "yes", "y", "production", "prod", "on"}


def parse_percent(value: Optional[Union[str, float]]) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    normalized = value.replace(",", ".")
    if not normalized:
        return None
    return float(normalized)


# ---------------------- UI components ----------------------


class AddEntryModal(discord.ui.Modal):
    def __init__(self, *, title: str = "Add market entry") -> None:
        super().__init__(title=title)
        self.city_input = discord.ui.TextInput(
            label="City",
            placeholder="Kingsport",
            min_length=1,
            max_length=100,
        )
        self.product_input = discord.ui.TextInput(
            label="Product",
            placeholder="Steel ingots",
            min_length=1,
            max_length=120,
        )
        self.price_input = discord.ui.TextInput(
            label="Price",
            placeholder="123.45",
            min_length=1,
            max_length=20,
        )
        self.trend_input = discord.ui.TextInput(
            label="Trend (up/down/flat)",
            placeholder="up",
            required=False,
            max_length=10,
        )
        self.percent_input = discord.ui.TextInput(
            label="Percent change",
            placeholder="10",
            required=False,
            max_length=10,
        )
        self.production_input = discord.ui.TextInput(
            label="Production city? (yes/no)",
            placeholder="yes",
            required=False,
            max_length=10,
        )

        for component in (
            self.city_input,
            self.product_input,
            self.price_input,
            self.trend_input,
            self.percent_input,
            self.production_input,
        ):
            self.add_item(component)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        price_raw = self.price_input.value.replace(",", ".").strip()
        try:
            price = float(price_raw)
        except ValueError:
            await interaction.response.send_message(
                "Could not parse price. Please enter a number.",
                ephemeral=True,
            )
            return

        percent_raw = (self.percent_input.value or "").strip()
        try:
            percent_value = parse_percent(percent_raw or None)
        except ValueError:
            await interaction.response.send_message(
                "Could not parse percent. Please enter a number or leave empty.",
                ephemeral=True,
            )
            return

        trend = (self.trend_input.value or "flat").strip().lower() or "flat"
        production_raw = (self.production_input.value or "").strip()

        try:
            entry = await run_db(
                insert_entry,
                self.city_input.value,
                self.product_input.value,
                price,
                trend,
                percent_value,
                parse_bool(production_raw),
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        embed = build_entry_confirmation_embed(entry)
        await interaction.response.send_message(embed=embed)


class RestrictedView(discord.ui.View):
    def __init__(self, user_id: Optional[int], *, timeout: Optional[float] = 180) -> None:
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.user_id is None or interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "Only the command invoker can use these controls.",
            ephemeral=True,
        )
        return False


class LatestView(RestrictedView):
    def __init__(self, user_id: Optional[int], limit: int) -> None:
        super().__init__(user_id)
        self.limit = limit

    async def _refresh(self, interaction: discord.Interaction) -> None:
        rows = await run_db(latest_prices, self.limit)
        embed = build_latest_embed(rows)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Show more", style=discord.ButtonStyle.primary)
    async def show_more(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.limit = min(self.limit + 5, 50)
        await self._refresh(interaction)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._refresh(interaction)

    @discord.ui.button(label="Add entry", style=discord.ButtonStyle.success)
    async def add_entry(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(AddEntryModal())


class RoutesView(RestrictedView):
    def __init__(self, user_id: Optional[int], limit: int) -> None:
        super().__init__(user_id)
        self.limit = limit

    async def _refresh(self, interaction: discord.Interaction) -> None:
        routes = await run_db(compute_routes, self.limit)
        embed = build_routes_embed(routes)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Show more", style=discord.ButtonStyle.primary)
    async def show_more(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.limit = min(self.limit + 5, 50)
        await self._refresh(interaction)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._refresh(interaction)
# ---------------------- Discord bot ----------------------

intents = discord.Intents.default()
intents.message_content = True


class TradeBot(commands.Bot):
    async def setup_hook(self) -> None:
        ensure_schema()
        await self.tree.sync()


bot = TradeBot(
    command_prefix=BOT_PREFIX,
    intents=intents,
    description=APP_TITLE,
    help_command=None,
)


@bot.event
async def on_ready():
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


@bot.hybrid_command(name="help", with_app_command=True, description="Show available commands")
async def help_command(ctx: commands.Context):
    help_text = (
        "**Trade Resonance Bot**\n"
        "Available commands (prefix `!` or `/` slash):\n"
        "`add <city> <product> <price> [trend] [percent] [production]` — add a new entry.\n"
        "`/add_modal` — open a guided modal to add an entry with validation.\n"
        "`latest [limit]` — show the latest prices per city.\n"
        "`routes [limit]` — show the most profitable trade routes.\n"
        "`product <product> [asc|desc]` — list prices for a specific product.\n"
        "`series <city> <product>` — display the price history for a pair.\n"
        "`suggest <city|product> [query]` — provide autocomplete suggestions.\n"
        "`export` — export all records to CSV.\n"
        "`import` (with a CSV attachment) — import records.\n"
    )
    await ctx.reply(help_text)


@bot.hybrid_command(
    name="add",
    with_app_command=True,
    description="Add a new market entry",
)
async def add_entry_command(
    ctx: commands.Context,
    city: str,
    product: str,
    price: float,
    trend: TrendLiteral = "flat",
    percent: Optional[float] = commands.parameter(
        default=None, description="Percent change (number)"
    ),
    production: bool = commands.parameter(
        default=False, description="Mark the city as a production location"
    ),
):
    try:
        percent_value = parse_percent(percent)
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

    embed = build_entry_confirmation_embed(entry)
    await ctx.reply(embed=embed)


@bot.tree.command(name="add_modal", description="Add a new market entry using a modal form")
async def add_modal_command(interaction: discord.Interaction):
    await interaction.response.send_modal(AddEntryModal())


@bot.hybrid_command(
    name="latest",
    with_app_command=True,
    description="Show the latest prices per city",
)
async def latest_command(
    ctx: commands.Context,
    limit: int = commands.parameter(
        default=DEFAULT_LIMIT, description="Number of rows to return (1-50)"
    ),
): 
    limit = max(1, min(limit, 50))
    rows = await run_db(latest_prices, limit)
    embed = build_latest_embed(rows)
    author_id = getattr(ctx.author, "id", None)
    view = LatestView(author_id, limit)
    await ctx.reply(embed=embed, view=view)


@bot.hybrid_command(
    name="routes",
    with_app_command=True,
    description="Show the most profitable trade routes",
)
async def routes_command(
    ctx: commands.Context,
    limit: int = commands.parameter(
        default=DEFAULT_LIMIT, description="Number of routes to show (1-50)"
    ),
):
    limit = max(1, min(limit, 50))
    routes = await run_db(compute_routes, limit)
    embed = build_routes_embed(routes)
    author_id = getattr(ctx.author, "id", None)
    view = RoutesView(author_id, limit)
    await ctx.reply(embed=embed, view=view)


@bot.hybrid_command(
    name="product",
    with_app_command=True,
    description="List prices for a specific product",
)
async def product_command(
    ctx: commands.Context, product: str, sort: SortLiteral = "asc"
):
    sort_value = (sort or "asc").lower()
    if sort_value not in ("asc", "desc"):
        sort_value = "asc"
    rows = await run_db(product_latest_prices, product, sort_value)
    if not rows:
        await ctx.reply("No data for the selected product.")
        return
    embed = build_product_embed(product, rows)
    await ctx.reply(embed=embed)


@bot.hybrid_command(
    name="series",
    with_app_command=True,
    description="Display price history for a city/product pair",
)
async def series_command(ctx: commands.Context, city: str, product: str):
    rows = await run_db(series, city, product)
    if not rows:
        await ctx.reply("No data for the selected city/product pair.")
        return
    embed = build_series_embed(city, product, rows)
    await ctx.reply(embed=embed)


@bot.hybrid_command(
    name="suggest",
    with_app_command=True,
    description="Provide autocomplete suggestions",
)
async def suggest_command(
    ctx: commands.Context,
    field: SuggestFieldLiteral,
    query: str = commands.parameter(default="", description="Optional search term"),
):
    field_value = field.lower()
    try:
        values = await run_db(suggest_values, field_value, query)
    except ValueError as exc:
        await ctx.reply(str(exc))
        return
    embed = build_suggest_embed(field_value, values)
    await ctx.reply(embed=embed)


@bot.hybrid_command(
    name="export",
    with_app_command=True,
    description="Export all records to CSV",
)
async def export_command(ctx: commands.Context):
    if ctx.interaction:
        await ctx.defer()
    data = await run_db(export_csv_bytes)
    buffer = io.BytesIO(data)
    buffer.seek(0)
    await ctx.reply(file=discord.File(buffer, filename="entries.csv"))


@bot.hybrid_command(
    name="import",
    with_app_command=True,
    description="Import records from a CSV attachment",
)
async def import_command(
    ctx: commands.Context,
    file: Optional[discord.Attachment] = commands.parameter(
        default=None, description="CSV file to import"
    ),
):
    attachment = file
    if attachment is None and ctx.message and ctx.message.attachments:
        attachment = ctx.message.attachments[0]
    if attachment is None:
        await ctx.reply("Attach a CSV file to the message.")
        return
    if ctx.interaction and not ctx.interaction.response.is_done():
        await ctx.defer()
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
