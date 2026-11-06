"""
Pure Python Native Desktop Personal Finance Application (INR ₹ Edition).

Tech Stack:
- UI: CustomTkinter (Modern Dark/Light mode desktop interface with multi-page navigation)
- Visualizations: Matplotlib (Embedded directly via FigureCanvasTkAgg)
- Database: SQLite3 (Local finance.db stored in the project directory)

Key Features:
- Indian Rupee (₹) currency formatting across all KPIs, charts, and tables
- Full CRUD (Add, Edit/Update any fed transaction, Delete, Seed/Clear Mock Data)
- Advanced Multi-Mode Pie/Donut Charts showing Income Modes, Expense Categories,
  or Dual Income + Expense breakdowns simultaneously
- Dedicated Weekly (W1–W5) & Monthly Data Explorer page with 'My Inputs Only' filter
"""

from __future__ import annotations

import calendar
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk
import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

# Force TkAgg backend for seamless embedding inside CustomTkinter frames
matplotlib.use("TkAgg")

# When packaged as a PyInstaller .exe, store finance.db next to the executable
if getattr(sys, "frozen", False):
    PROJECT_DIR = Path(sys.executable).resolve().parent
else:
    PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = PROJECT_DIR / "finance.db"
CURRENCY_SYMBOL = "₹"

INCOME_CATEGORIES: List[str] = [
    "Salary (Bank Credit)",
    "Freelance & Consulting",
    "Business / Side Hustle",
    "Investments & Dividends",
    "UPI / Direct Transfer",
    "Rental Income",
    "Bonus & Cashback",
    "Other Income",
]

EXPENSE_CATEGORIES: List[str] = [
    "Housing & Rent",
    "Groceries & Kirana",
    "Dining & Food Delivery",
    "Utilities, Electricity & Wifi",
    "Transport, Metro & Fuel",
    "Entertainment & OTT",
    "Healthcare & Medical",
    "Shopping & Electronics",
]

WEEK_BUCKETS: List[Tuple[str, int, int]] = [
    ("Week 1 (Days 1–7)", 1, 7),
    ("Week 2 (Days 8–14)", 8, 14),
    ("Week 3 (Days 15–21)", 15, 21),
    ("Week 4 (Days 22–28)", 22, 28),
    ("Week 5 (Days 29–31)", 29, 31),
]

# Modern high-contrast color palette for dark and light modes
THEME_PALETTE: Dict[str, Dict[str, str]] = {
    "Dark": {
        "window_bg": "#0f172a",
        "card_bg": "#1e293b",
        "card_border": "#334155",
        "sidebar_bg": "#111827",
        "input_bg": "#0f172a",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "income": "#10b981",
        "expense": "#f43f5e",
        "balance": "#38bdf8",
        "edit_accent": "#f59e0b",
        "nav_active": "#2563eb",
        "nav_inactive": "#1e293b",
        "grid_line": "#334155",
        "row_bg": "#0f172a",
    },
    "Light": {
        "window_bg": "#f1f5f9",
        "card_bg": "#ffffff",
        "card_border": "#cbd5e1",
        "sidebar_bg": "#e2e8f0",
        "input_bg": "#f8fafc",
        "text_primary": "#0f172a",
        "text_secondary": "#475569",
        "income": "#059669",
        "expense": "#e11d48",
        "balance": "#0284c7",
        "edit_accent": "#d97706",
        "nav_active": "#2563eb",
        "nav_inactive": "#cbd5e1",
        "grid_line": "#e2e8f0",
        "row_bg": "#f8fafc",
    },
}

EXPENSE_PIE_COLORS: List[str] = [
    "#f43f5e",  # Rose
    "#8b5cf6",  # Violet
    "#f59e0b",  # Amber
    "#06b6d4",  # Cyan
    "#ec4899",  # Pink
    "#3b82f6",  # Blue
    "#14b8a6",  # Teal
    "#eab308",  # Yellow
]

INCOME_PIE_COLORS: List[str] = [
    "#10b981",  # Emerald
    "#06b6d4",  # Cyan
    "#3b82f6",  # Blue
    "#14b8a6",  # Teal
    "#84cc16",  # Lime
    "#6366f1",  # Indigo
    "#22c55e",  # Green
    "#0ea5e9",  # Sky
]


def format_inr(amount: float, include_decimals: bool = True) -> str:
    """
    Format a numeric value in Indian Rupee (₹) notation (e.g. ₹1,25,400.00).
    """
    is_negative = amount < 0
    val = abs(amount)
    if include_decimals:
        int_part_str, dec_part_str = f"{val:.2f}".split(".")
    else:
        int_part_str = f"{round(val):.0f}"
        dec_part_str = ""

    if len(int_part_str) > 3:
        last_three = int_part_str[-3:]
        remaining = int_part_str[:-3]
        groups: List[str] = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_int = ",".join(groups) + "," + last_three
    else:
        formatted_int = int_part_str

    prefix = f"-{CURRENCY_SYMBOL}" if is_negative else CURRENCY_SYMBOL
    if include_decimals:
        return f"{prefix}{formatted_int}.{dec_part_str}"
    return f"{prefix}{formatted_int}"


def day_to_week_number(day_num: int) -> int:
    """Map day of month (1..31) to week number (1..5)."""
    return min(((max(day_num, 1) - 1) // 7) + 1, 5)


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the transactions table and ensure the `is_mock` column exists."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_date TEXT NOT NULL,
            tx_type TEXT NOT NULL CHECK(tx_type IN ('Income', 'Expense')),
            category TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            note TEXT DEFAULT '',
            is_mock INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("PRAGMA table_info(transactions)")
    columns = {row[1] for row in cursor.fetchall()}
    if "is_mock" not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN is_mock INTEGER DEFAULT 0")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_transactions_date_type
        ON transactions (tx_date, tx_type)
        """
    )
    conn.commit()


def populate_mock_data(
    db_path: Path = DB_PATH,
    target_month: Optional[str] = None,
    force: bool = False,
) -> int:
    """
    Populate the SQLite database with realistic INR (₹) mock monthly and weekly
    transactions across multiple Income Modes and Expense Categories.
    """
    if target_month is None:
        target_month = datetime.now().strftime("%Y-%m")

    year, month = map(int, target_month.split("-"))
    max_day = calendar.monthrange(year, month)[1]

    def clamp_day(day: int) -> str:
        safe_day = min(max(day, 1), max_day)
        return f"{target_month}-{safe_day:02d}"

    with sqlite3.connect(db_path) as conn:
        ensure_schema(conn)
        cursor = conn.cursor()

        if force:
            cursor.execute(
                "DELETE FROM transactions WHERE substr(tx_date, 1, 7) = ? AND is_mock = 1",
                (target_month,),
            )

        cursor.execute(
            "SELECT COUNT(*) FROM transactions WHERE substr(tx_date, 1, 7) = ?",
            (target_month,),
        )
        existing_count = cursor.fetchone()[0]
        if existing_count > 0 and not force:
            return 0

        # Realistic Indian Rupee (₹) transactions across diverse Income Modes & Expense Categories
        mock_entries: List[Tuple[str, str, str, float, str, int]] = [
            # Week 1 (Days 1–7)
            (clamp_day(1), "Income", "Salary (Bank Credit)", 85000.00, "Monthly salary credit (HDFC NEFT)", 1),
            (clamp_day(2), "Expense", "Housing & Rent", 24000.00, "2BHK apartment monthly rent", 1),
            (clamp_day(3), "Expense", "Groceries & Kirana", 3850.00, "DMart monthly staples & groceries", 1),
            (clamp_day(4), "Income", "Rental Income", 12000.00, "Shop / parking space monthly rent", 1),
            (clamp_day(5), "Expense", "Utilities, Electricity & Wifi", 2650.00, "Electricity bill & JioFiber broadband", 1),
            (clamp_day(6), "Expense", "Dining & Food Delivery", 1250.00, "Weekend family dinner", 1),
            (clamp_day(7), "Income", "Freelance & Consulting", 15000.00, "Python automation client project", 1),
            # Week 2 (Days 8–14)
            (clamp_day(8), "Expense", "Transport, Metro & Fuel", 2200.00, "Petrol full tank & metro card recharge", 1),
            (clamp_day(10), "Expense", "Groceries & Kirana", 1640.00, "Fresh vegetables, fruits & dairy", 1),
            (clamp_day(12), "Expense", "Entertainment & OTT", 999.00, "OTT subscriptions & movie tickets", 1),
            (clamp_day(14), "Income", "Investments & Dividends", 6500.00, "Nifty 50 ETF & equity dividend payout", 1),
            (clamp_day(14), "Expense", "Healthcare & Medical", 1800.00, "Routine health checkup & pharmacy", 1),
            # Week 3 (Days 15–21)
            (clamp_day(16), "Expense", "Shopping & Electronics", 5400.00, "Wireless keyboard & apparel", 1),
            (clamp_day(17), "Income", "Business / Side Hustle", 9500.00, "Weekend workshop & digital templates", 1),
            (clamp_day(18), "Expense", "Groceries & Kirana", 2150.00, "Mid-month grocery restock", 1),
            (clamp_day(20), "Expense", "Dining & Food Delivery", 980.00, "Swiggy / Zomato weekend order", 1),
            (clamp_day(21), "Expense", "Utilities, Electricity & Wifi", 1199.00, "Mobile postpaid & LPG cylinder", 1),
            # Week 4 (Days 22–28)
            (clamp_day(23), "Income", "Freelance & Consulting", 12500.00, "Dashboard analytics consulting", 1),
            (clamp_day(24), "Expense", "Transport, Metro & Fuel", 1750.00, "Fuel refill & cab rides", 1),
            (clamp_day(25), "Expense", "Groceries & Kirana", 1490.00, "Weekly fresh groceries", 1),
            (clamp_day(26), "Expense", "Entertainment & OTT", 1100.00, "Badminton court booking & outing", 1),
            (clamp_day(27), "Income", "Bonus & Cashback", 8000.00, "Quarterly spot performance bonus", 1),
        ]

        cursor.executemany(
            """
            INSERT INTO transactions (tx_date, tx_type, category, amount, note, is_mock)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            mock_entries,
        )
        conn.commit()
        return len(mock_entries)


class App(ctk.CTk):
    """
    Main Standalone Personal Finance Application Window (INR ₹ Edition).

    Features:
    - Full CRUD: Create, Read, Edit/Update any fed transaction (in-sidebar edit mode
      AND quick-edit popup dialog), and Delete.
    - Advanced Multi-Mode Pie/Donut Chart: Toggle between 'Income + Expense (Dual)',
      'Income Modes (₹)', and 'Expense Categories (₹)' on both pages.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        super().__init__()

        self.db_path: Path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.current_month: str = datetime.now().strftime("%Y-%m")
        self.appearance_mode: str = "Dark"
        self.active_page: str = "dashboard"
        self.editing_tx_id: Optional[int] = None  # Tracks transaction ID currently being edited

        # Configure CustomTkinter global appearance
        ctk.set_appearance_mode(self.appearance_mode)
        ctk.set_default_color_theme("blue")

        # Configure standalone window properties
        self.title("PulseFinance INR (₹) — Full Edit & Advanced Income/Expense Analytics")
        self.geometry("1400x880")
        self.minsize(1180, 750)
        self.configure(fg_color=self._color("window_bg"))

        # 1. Initialize SQLite database & populate realistic INR mock data
        self.init_database()

        # 2. Build CustomTkinter UI hierarchy (Sidebar + Both Pages)
        self.setup_ui()

        # 3. Initialize embedded Matplotlib canvases for both pages and render
        self.init_matplotlib_canvases()
        self.refresh_all_views()
        self.switch_page("dashboard")

        # Clean shutdown handler
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # =========================================================================
    # 1. DATABASE CONNECTION & SQLITE CRUD OPERATIONS
    # =========================================================================

    def init_database(self) -> None:
        """Establish persistent SQLite connection, migrate schema, and seed INR mock data."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM transactions WHERE note = 'Monthly base salary (Part 1)'"
        )
        if cursor.fetchone()[0] > 0:
            cursor.execute("DELETE FROM transactions")
            self.conn.commit()

        populate_mock_data(self.db_path, self.current_month, force=False)

    def get_available_months(self) -> List[str]:
        """Return sorted list of distinct YYYY-MM months present in the database."""
        assert self.conn is not None
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT DISTINCT substr(tx_date, 1, 7) AS ym FROM transactions ORDER BY ym DESC"
        )
        months = [str(r["ym"]) for r in cursor.fetchall() if r["ym"]]
        if self.current_month not in months:
            months.insert(0, self.current_month)
        return months

    def _source_clause(self, only_user_input: bool) -> str:
        """Return SQL filter snippet when filtering to user-entered records only."""
        return " AND COALESCE(is_mock, 0) = 0 " if only_user_input else ""

    def fetch_transaction_by_id(self, tx_id: int) -> Optional[sqlite3.Row]:
        """Fetch a single transaction record by its primary key ID for editing."""
        assert self.conn is not None
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, tx_date, tx_type, category, amount, note, COALESCE(is_mock, 0) AS is_mock
            FROM transactions
            WHERE id = ?
            """,
            (tx_id,),
        )
        return cursor.fetchone()

    def fetch_monthly_summary(
        self,
        month_str: Optional[str] = None,
        only_user_input: bool = False,
        week_num: Optional[int] = None,
    ) -> Dict[str, float]:
        """
        Return total income, total expenses, net balance, and counts for a month
        (and optionally filtered to a specific week 1..5 or user inputs only).
        """
        assert self.conn is not None
        target_ym = month_str or self.current_month
        params: List[object] = [target_ym]
        extra_sql = self._source_clause(only_user_input)

        if week_num is not None and 1 <= week_num <= 5:
            start_day = (week_num - 1) * 7 + 1
            end_day = 31 if week_num == 5 else week_num * 7
            extra_sql += " AND CAST(substr(tx_date, 9, 2) AS INTEGER) BETWEEN ? AND ? "
            params.extend([start_day, end_day])

        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT
                tx_type,
                COALESCE(SUM(amount), 0.0) AS total_amount,
                COUNT(*) AS tx_count
            FROM transactions
            WHERE substr(tx_date, 1, 7) = ?
              {extra_sql}
            GROUP BY tx_type
            """,
            params,
        )
        summary: Dict[str, float] = {
            "income": 0.0,
            "expense": 0.0,
            "net_balance": 0.0,
            "income_count": 0,
            "expense_count": 0,
        }
        for row in cursor.fetchall():
            if row["tx_type"] == "Income":
                summary["income"] = float(row["total_amount"])
                summary["income_count"] = int(row["tx_count"])
            elif row["tx_type"] == "Expense":
                summary["expense"] = float(row["total_amount"])
                summary["expense_count"] = int(row["tx_count"])

        summary["net_balance"] = summary["income"] - summary["expense"]
        return summary

    def fetch_daily_series(
        self,
        month_str: Optional[str] = None,
        only_user_input: bool = False,
    ) -> Tuple[List[int], List[float], List[float], List[float], List[float]]:
        """
        Compute daily and cumulative income vs. expense series across all days
        of the active month for the Matplotlib line chart.
        """
        assert self.conn is not None
        target_ym = month_str or self.current_month
        year, month = map(int, target_ym.split("-"))
        num_days = calendar.monthrange(year, month)[1]

        daily_income: Dict[int, float] = {d: 0.0 for d in range(1, num_days + 1)}
        daily_expense: Dict[int, float] = {d: 0.0 for d in range(1, num_days + 1)}

        extra_sql = self._source_clause(only_user_input)
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT
                CAST(substr(tx_date, 9, 2) AS INTEGER) AS day_num,
                tx_type,
                SUM(amount) AS daily_total
            FROM transactions
            WHERE substr(tx_date, 1, 7) = ?
              {extra_sql}
            GROUP BY day_num, tx_type
            ORDER BY day_num ASC
            """,
            (target_ym,),
        )
        for row in cursor.fetchall():
            day_num = int(row["day_num"])
            if 1 <= day_num <= num_days:
                if row["tx_type"] == "Income":
                    daily_income[day_num] = float(row["daily_total"])
                elif row["tx_type"] == "Expense":
                    daily_expense[day_num] = float(row["daily_total"])

        days = list(range(1, num_days + 1))
        inc_discrete = [daily_income[d] for d in days]
        exp_discrete = [daily_expense[d] for d in days]

        inc_cumulative: List[float] = []
        exp_cumulative: List[float] = []
        running_inc = 0.0
        running_exp = 0.0
        for d in days:
            running_inc += daily_income[d]
            running_exp += daily_expense[d]
            inc_cumulative.append(running_inc)
            exp_cumulative.append(running_exp)

        return days, inc_discrete, exp_discrete, inc_cumulative, exp_cumulative

    def fetch_weekly_series(
        self,
        month_str: Optional[str] = None,
        only_user_input: bool = False,
    ) -> Tuple[List[str], List[float], List[float]]:
        """
        Aggregate Income and Expense totals by Week 1..Week 5 for the selected month.
        """
        assert self.conn is not None
        target_ym = month_str or self.current_month
        extra_sql = self._source_clause(only_user_input)

        week_inc: Dict[int, float] = {w: 0.0 for w in range(1, 6)}
        week_exp: Dict[int, float] = {w: 0.0 for w in range(1, 6)}

        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT
                CAST(substr(tx_date, 9, 2) AS INTEGER) AS day_num,
                tx_type,
                SUM(amount) AS total_amount
            FROM transactions
            WHERE substr(tx_date, 1, 7) = ?
              {extra_sql}
            GROUP BY day_num, tx_type
            """,
            (target_ym,),
        )
        for row in cursor.fetchall():
            w_idx = day_to_week_number(int(row["day_num"]))
            if row["tx_type"] == "Income":
                week_inc[w_idx] += float(row["total_amount"])
            elif row["tx_type"] == "Expense":
                week_exp[w_idx] += float(row["total_amount"])

        labels = [
            "Week 1\n(1–7)",
            "Week 2\n(8–14)",
            "Week 3\n(15–21)",
            "Week 4\n(22–28)",
            "Week 5\n(29–31)",
        ]
        inc_vals = [week_inc[w] for w in range(1, 6)]
        exp_vals = [week_exp[w] for w in range(1, 6)]
        return labels, inc_vals, exp_vals

    def fetch_monthly_comparison_series(
        self,
        only_user_input: bool = False,
    ) -> Tuple[List[str], List[float], List[float]]:
        """
        Aggregate Income and Expense totals across available months for Monthly view.
        """
        assert self.conn is not None
        extra_sql = self._source_clause(only_user_input)
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT
                substr(tx_date, 1, 7) AS ym,
                tx_type,
                SUM(amount) AS total_amount
            FROM transactions
            WHERE 1=1
              {extra_sql}
            GROUP BY ym, tx_type
            ORDER BY ym ASC
            """
        )
        months_map: Dict[str, Dict[str, float]] = {}
        for row in cursor.fetchall():
            ym = str(row["ym"])
            if ym not in months_map:
                months_map[ym] = {"Income": 0.0, "Expense": 0.0}
            months_map[ym][str(row["tx_type"])] = float(row["total_amount"])

        if not months_map:
            months_map[self.current_month] = {"Income": 0.0, "Expense": 0.0}

        labels = list(months_map.keys())
        inc_vals = [months_map[m]["Income"] for m in labels]
        exp_vals = [months_map[m]["Expense"] for m in labels]
        return labels, inc_vals, exp_vals

    def fetch_category_breakdown(
        self,
        tx_type: str = "Expense",
        month_str: Optional[str] = None,
        only_user_input: bool = False,
        week_num: Optional[int] = None,
    ) -> List[Tuple[str, float]]:
        """
        Fetch category/mode totals grouped by `category` for either 'Income' (Income Modes)
        or 'Expense' (Expense Categories) for the selected month/week/source.
        """
        assert self.conn is not None
        target_ym = month_str or self.current_month
        params: List[object] = [tx_type, target_ym]
        extra_sql = self._source_clause(only_user_input)

        if week_num is not None and 1 <= week_num <= 5:
            start_day = (week_num - 1) * 7 + 1
            end_day = 31 if week_num == 5 else week_num * 7
            extra_sql += " AND CAST(substr(tx_date, 9, 2) AS INTEGER) BETWEEN ? AND ? "
            params.extend([start_day, end_day])

        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT
                category,
                SUM(amount) AS category_total
            FROM transactions
            WHERE tx_type = ?
              AND substr(tx_date, 1, 7) = ?
              {extra_sql}
            GROUP BY category
            ORDER BY category_total DESC
            """,
            params,
        )
        return [(str(row["category"]), float(row["category_total"])) for row in cursor.fetchall()]

    def fetch_filtered_transactions(
        self,
        month_str: Optional[str] = None,
        only_user_input: bool = False,
        week_num: Optional[int] = None,
        limit: int = 100,
    ) -> List[sqlite3.Row]:
        """Fetch transactions matching the selected month, week, and source filter."""
        assert self.conn is not None
        target_ym = month_str or self.current_month
        params: List[object] = [target_ym]
        extra_sql = self._source_clause(only_user_input)

        if week_num is not None and 1 <= week_num <= 5:
            start_day = (week_num - 1) * 7 + 1
            end_day = 31 if week_num == 5 else week_num * 7
            extra_sql += " AND CAST(substr(tx_date, 9, 2) AS INTEGER) BETWEEN ? AND ? "
            params.extend([start_day, end_day])

        params.append(limit)
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, tx_date, tx_type, category, amount, note, COALESCE(is_mock, 0) AS is_mock
            FROM transactions
            WHERE substr(tx_date, 1, 7) = ?
              {extra_sql}
            ORDER BY tx_date DESC, id DESC
            LIMIT ?
            """,
            params,
        )
        return cursor.fetchall()

    def insert_transaction(
        self,
        tx_date: str,
        tx_type: str,
        category: str,
        amount: float,
        note: str = "",
        is_mock: int = 0,
    ) -> None:
        """Write a new income or expense record directly to the SQLite database."""
        assert self.conn is not None
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO transactions (tx_date, tx_type, category, amount, note, is_mock)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (tx_date, tx_type, category, round(amount, 2), note.strip(), is_mock),
        )
        self.conn.commit()

    def update_transaction(
        self,
        tx_id: int,
        tx_date: str,
        tx_type: str,
        category: str,
        amount: float,
        note: str = "",
    ) -> None:
        """
        Update any existing transaction record in SQLite (`is_mock` becomes 0 so edited
        entries are treated as user-confirmed data).
        """
        assert self.conn is not None
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE transactions
            SET tx_date = ?,
                tx_type = ?,
                category = ?,
                amount = ?,
                note = ?,
                is_mock = 0
            WHERE id = ?
            """,
            (tx_date, tx_type, category, round(amount, 2), note.strip(), tx_id),
        )
        self.conn.commit()

    def delete_transaction(self, tx_id: int) -> None:
        """Delete a single transaction by its primary key ID."""
        assert self.conn is not None
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        self.conn.commit()

    def clear_mock_transactions(self) -> int:
        """Remove all seeded mock records (`is_mock = 1`) so only user inputs remain."""
        assert self.conn is not None
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM transactions WHERE COALESCE(is_mock, 0) = 1")
        removed = cursor.rowcount
        self.conn.commit()
        return removed

    # =========================================================================
    # 2. CUSTOMTKINTER UI LAYOUT & MULTI-PAGE RENDERING
    # =========================================================================

    def _color(self, key: str) -> str:
        """Retrieve active theme color hex string."""
        return THEME_PALETTE.get(self.appearance_mode, THEME_PALETTE["Dark"])[key]

    def setup_ui(self) -> None:
        """Configure root grid layout, left sidebar (with navigation + add/edit form), and 2 pages."""
        self.grid_columnconfigure(0, weight=0, minsize=345)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Sidebar: Navigation + Add / Edit Form
        self.build_sidebar_form()

        # Right Host Container for Pages
        self.pages_host = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.pages_host.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        self.pages_host.grid_columnconfigure(0, weight=1)
        self.pages_host.grid_rowconfigure(0, weight=1)

        # Page 1: Primary Monthly Dashboard
        self.dashboard_page = ctk.CTkFrame(self.pages_host, fg_color="transparent")
        self.dashboard_page.grid(row=0, column=0, sticky="nsew")
        self.dashboard_page.grid_columnconfigure(0, weight=1)
        self.dashboard_page.grid_rowconfigure(0, weight=0)  # Top Header
        self.dashboard_page.grid_rowconfigure(1, weight=0)  # Monthly KPI Cards
        self.dashboard_page.grid_rowconfigure(2, weight=1)  # Embedded Charts
        self.dashboard_page.grid_rowconfigure(3, weight=0)  # Recent Feed (with Edit/Delete)

        self.build_dashboard_header()
        self.build_dashboard_kpis()
        self.build_chart_containers()
        self.build_recent_transactions_panel()

        # Page 2: Separate Monthly & Weekly Analytics Page (With Full Edit & Income Modes Pie)
        self.analytics_page = ctk.CTkFrame(self.pages_host, fg_color="transparent")
        self.analytics_page.grid(row=0, column=0, sticky="nsew")
        self.analytics_page.grid_columnconfigure(0, weight=1)
        self.analytics_page.grid_rowconfigure(0, weight=0)  # Page Header + Filter Bar
        self.analytics_page.grid_rowconfigure(1, weight=0)  # Weekly/Monthly Summary KPIs
        self.analytics_page.grid_rowconfigure(2, weight=1)  # Weekly/Monthly Charts
        self.analytics_page.grid_rowconfigure(3, weight=1)  # Full Editable Table

        self.build_analytics_page()

    def build_sidebar_form(self) -> None:
        """Build the left sidebar with Page Navigation, Add/Edit Form, and Data Utilities."""
        self.sidebar_frame = ctk.CTkFrame(
            self,
            width=345,
            corner_radius=16,
            fg_color=self._color("sidebar_bg"),
            border_width=1,
            border_color=self._color("card_border"),
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 8), pady=20)
        self.sidebar_frame.grid_propagate(False)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        # App Brand Title
        brand_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 6))

        self.title_label = ctk.CTkLabel(
            brand_frame,
            text="PulseFinance ₹ (INR)",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=self._color("text_primary"),
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            brand_frame,
            text="Full Edit CRUD • Income & Expense Pie",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=self._color("text_secondary"),
        )
        self.subtitle_label.pack(anchor="w", pady=(1, 0))

        # Page Navigation Switcher Card
        self.nav_card = ctk.CTkFrame(
            self.sidebar_frame,
            corner_radius=12,
            fg_color=self._color("card_bg"),
            border_width=1,
            border_color=self._color("card_border"),
        )
        self.nav_card.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 8))
        self.nav_card.grid_columnconfigure(0, weight=1)
        self.nav_card.grid_columnconfigure(1, weight=1)

        nav_lbl = ctk.CTkLabel(
            self.nav_card,
            text="NAVIGATION PAGES",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self._color("text_secondary"),
        )
        nav_lbl.grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 4))

        self.nav_dash_btn = ctk.CTkButton(
            self.nav_card,
            text="1. Overview",
            command=lambda: self.switch_page("dashboard"),
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        self.nav_dash_btn.grid(row=1, column=0, sticky="ew", padx=(10, 4), pady=(0, 10))

        self.nav_analytics_btn = ctk.CTkButton(
            self.nav_card,
            text="2. Weekly & Monthly",
            command=lambda: self.switch_page("analytics"),
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        self.nav_analytics_btn.grid(row=1, column=1, sticky="ew", padx=(4, 10), pady=(0, 10))

        # Data Entry & Edit Form Card Container
        self.form_card = ctk.CTkFrame(
            self.sidebar_frame,
            corner_radius=14,
            fg_color=self._color("card_bg"),
            border_width=1,
            border_color=self._color("card_border"),
        )
        self.form_card.grid(row=2, column=0, sticky="ew", padx=16, pady=4)
        self.form_card.grid_columnconfigure(0, weight=1)

        self.form_header_lbl = ctk.CTkLabel(
            self.form_card,
            text="Add New Entry (₹ INR)",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=self._color("text_primary"),
        )
        self.form_header_lbl.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 6))

        # Transaction Type Segmented Control
        type_label = ctk.CTkLabel(
            self.form_card,
            text="TRANSACTION TYPE",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self._color("text_secondary"),
        )
        type_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 2))

        self.tx_type_var = ctk.StringVar(value="Expense")
        self.tx_type_selector = ctk.CTkSegmentedButton(
            self.form_card,
            values=["Expense", "Income"],
            variable=self.tx_type_var,
            command=self.on_transaction_type_change,
            height=33,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            selected_color="#f43f5e",
            selected_hover_color="#e11d48",
        )
        self.tx_type_selector.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))

        # Date Entry
        date_label = ctk.CTkLabel(
            self.form_card,
            text="DATE (YYYY-MM-DD)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self._color("text_secondary"),
        )
        date_label.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 2))

        self.date_entry = ctk.CTkEntry(
            self.form_card,
            height=33,
            corner_radius=8,
            placeholder_text="YYYY-MM-DD",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.date_entry.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 8))
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

        # Amount Entry in INR
        amount_label = ctk.CTkLabel(
            self.form_card,
            text="AMOUNT IN INR (₹)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self._color("text_secondary"),
        )
        amount_label.grid(row=5, column=0, sticky="w", padx=16, pady=(0, 2))

        self.amount_entry = ctk.CTkEntry(
            self.form_card,
            height=33,
            corner_radius=8,
            placeholder_text="e.g. 2500",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.amount_entry.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 8))

        # Category / Income Mode ComboBox (Editable for custom modes!)
        self.category_field_label = ctk.CTkLabel(
            self.form_card,
            text="EXPENSE CATEGORY (OR TYPE CUSTOM)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self._color("text_secondary"),
        )
        self.category_field_label.grid(row=7, column=0, sticky="w", padx=16, pady=(0, 2))

        self.category_combobox = ctk.CTkComboBox(
            self.form_card,
            values=EXPENSE_CATEGORIES,
            height=33,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.category_combobox.set(EXPENSE_CATEGORIES[0])
        self.category_combobox.grid(row=8, column=0, sticky="ew", padx=16, pady=(0, 8))

        # Optional Note Entry
        note_label = ctk.CTkLabel(
            self.form_card,
            text="DESCRIPTION / NOTE",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self._color("text_secondary"),
        )
        note_label.grid(row=9, column=0, sticky="w", padx=16, pady=(0, 2))

        self.note_entry = ctk.CTkEntry(
            self.form_card,
            height=33,
            corner_radius=8,
            placeholder_text="e.g. UPI transfer / Kirana store",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.note_entry.grid(row=10, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.note_entry.bind("<Return>", lambda _event: self.handle_save_or_update_transaction())
        self.amount_entry.bind("<Return>", lambda _event: self.handle_save_or_update_transaction())

        # Submit / Update Button Row
        self.action_btn_row = ctk.CTkFrame(self.form_card, fg_color="transparent")
        self.action_btn_row.grid(row=11, column=0, sticky="ew", padx=16, pady=(2, 6))
        self.action_btn_row.grid_columnconfigure(0, weight=1)

        self.submit_btn = ctk.CTkButton(
            self.action_btn_row,
            text="+ Save Entry (₹)",
            command=self.handle_save_or_update_transaction,
            height=36,
            corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#3b82f6",
            hover_color="#2563eb",
        )
        self.submit_btn.grid(row=0, column=0, sticky="ew")

        self.cancel_edit_btn = ctk.CTkButton(
            self.action_btn_row,
            text="Cancel",
            command=self.cancel_edit_mode,
            width=75,
            height=36,
            corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#475569",
            hover_color="#334155",
        )
        # Hidden until user clicks 'Edit' on a row

        # Validation / Feedback Label
        self.status_label = ctk.CTkLabel(
            self.form_card,
            text="Click '✎ Edit' on any row to modify existing data",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=self._color("text_secondary"),
            wraplength=270,
        )
        self.status_label.grid(row=12, column=0, sticky="ew", padx=16, pady=(0, 10))

        # Bottom Controls (Mock Data Re-seeder, Clear Mock Data, & Theme Switcher)
        self.sidebar_frame.grid_rowconfigure(3, weight=1)

        controls_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        controls_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 14))
        controls_frame.grid_columnconfigure(0, weight=1)
        controls_frame.grid_columnconfigure(1, weight=1)

        self.reset_mock_btn = ctk.CTkButton(
            controls_frame,
            text="Seed ₹ Mock",
            command=self.handle_reset_mock_data,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=self._color("card_border"),
            text_color=self._color("text_primary"),
            hover_color=self._color("card_bg"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self.reset_mock_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 6))

        self.clear_mock_btn = ctk.CTkButton(
            controls_frame,
            text="Only My Input",
            command=self.handle_clear_mock_data,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=self._color("card_border"),
            text_color=self._color("text_primary"),
            hover_color=self._color("card_bg"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self.clear_mock_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6))

        self.theme_menu = ctk.CTkOptionMenu(
            controls_frame,
            values=["Dark", "Light"],
            command=self.toggle_appearance_mode,
            height=30,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.theme_menu.set(self.appearance_mode)
        self.theme_menu.grid(row=1, column=0, columnspan=2, sticky="ew")

    # -------------------------------------------------------------------------
    # PAGE 1: PRIMARY OVERVIEW DASHBOARD
    # -------------------------------------------------------------------------

    def build_dashboard_header(self) -> None:
        """Build the top bar displaying the active month title and quick page jump button."""
        header_frame = ctk.CTkFrame(self.dashboard_page, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(0, weight=1)

        month_dt = datetime.strptime(self.current_month, "%Y-%m")
        month_pretty = month_dt.strftime("%B %Y")

        self.dashboard_title = ctk.CTkLabel(
            header_frame,
            text=f"Monthly Financial Dashboard (INR ₹) — {month_pretty}",
            font=ctk.CTkFont(family="Segoe UI", size=21, weight="bold"),
            text_color=self._color("text_primary"),
        )
        self.dashboard_title.grid(row=0, column=0, sticky="w")

        self.open_weekly_btn = ctk.CTkButton(
            header_frame,
            text="Open Weekly & Monthly Analytics Page →",
            command=lambda: self.switch_page("analytics"),
            height=34,
            corner_radius=8,
            fg_color="#6366f1",
            hover_color="#4f46e5",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        self.open_weekly_btn.grid(row=0, column=1, sticky="e", padx=4)

    def build_dashboard_kpis(self) -> None:
        """Build the three primary Monthly Dashboard KPI cards at the top of Page 1."""
        self.kpi_container = ctk.CTkFrame(self.dashboard_page, fg_color="transparent")
        self.kpi_container.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for col in range(3):
            self.kpi_container.grid_columnconfigure(col, weight=1, uniform="kpi")

        self.income_card, self.income_val_lbl, self.income_sub_lbl = self._create_kpi_card(
            parent=self.kpi_container,
            column=0,
            title="TOTAL MONTHLY INCOME (₹)",
            accent_color=self._color("income"),
            padx=(0, 8),
        )

        self.expense_card, self.expense_val_lbl, self.expense_sub_lbl = self._create_kpi_card(
            parent=self.kpi_container,
            column=1,
            title="TOTAL MONTHLY EXPENSES (₹)",
            accent_color=self._color("expense"),
            padx=(8, 8),
        )

        self.balance_card, self.balance_val_lbl, self.balance_sub_lbl = self._create_kpi_card(
            parent=self.kpi_container,
            column=2,
            title="MONTHLY NET BALANCE (₹)",
            accent_color=self._color("balance"),
            padx=(8, 0),
        )

    def _create_kpi_card(
        self,
        parent: ctk.CTkFrame,
        column: int,
        title: str,
        accent_color: str,
        padx: Tuple[int, int],
    ) -> Tuple[ctk.CTkFrame, ctk.CTkLabel, ctk.CTkLabel]:
        """Helper to construct a styled rounded KPI card with title, metric, and subtitle."""
        card = ctk.CTkFrame(
            parent,
            corner_radius=14,
            fg_color=self._color("card_bg"),
            border_width=1,
            border_color=self._color("card_border"),
        )
        card.grid(row=0, column=column, sticky="nsew", padx=padx)

        accent_bar = ctk.CTkFrame(
            card,
            height=4,
            corner_radius=2,
            fg_color=accent_color,
        )
        accent_bar.pack(fill="x", padx=18, pady=(10, 4))

        title_lbl = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=self._color("text_secondary"),
        )
        title_lbl.pack(anchor="w", padx=18, pady=(1, 1))

        val_lbl = ctk.CTkLabel(
            card,
            text="₹0.00",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=accent_color,
        )
        val_lbl.pack(anchor="w", padx=18, pady=(0, 2))

        sub_lbl = ctk.CTkLabel(
            card,
            text="0 transactions this month",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=self._color("text_secondary"),
        )
        sub_lbl.pack(anchor="w", padx=18, pady=(0, 10))

        return card, val_lbl, sub_lbl

    def build_chart_containers(self) -> None:
        """Build side-by-side CustomTkinter frames on Page 1 to host embedded Matplotlib charts."""
        self.charts_row = ctk.CTkFrame(self.dashboard_page, fg_color="transparent")
        self.charts_row.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        self.charts_row.grid_columnconfigure(0, weight=11)
        self.charts_row.grid_columnconfigure(1, weight=10)
        self.charts_row.grid_rowconfigure(0, weight=1)

        # Left Container: Income vs. Expenses Line Chart
        self.line_chart_card = ctk.CTkFrame(
            self.charts_row,
            corner_radius=14,
            fg_color=self._color("card_bg"),
            border_width=1,
            border_color=self._color("card_border"),
        )
        self.line_chart_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.line_chart_card.grid_rowconfigure(1, weight=1)
        self.line_chart_card.grid_columnconfigure(0, weight=1)

        self.line_chart_title = ctk.CTkLabel(
            self.line_chart_card,
            text="Income vs. Expenses Over Month (Cumulative ₹ Trajectory)",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=self._color("text_primary"),
        )
        self.line_chart_title.grid(row=0, column=0, sticky="w", padx=18, pady=(12, 4))

        self.line_canvas_holder = ctk.CTkFrame(self.line_chart_card, fg_color="transparent")
        self.line_canvas_holder.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # Right Container: Advanced Multi-Mode Pie & Donut Chart (Income Modes + Expenses)
        self.donut_chart_card = ctk.CTkFrame(
            self.charts_row,
            corner_radius=14,
            fg_color=self._color("card_bg"),
            border_width=1,
            border_color=self._color("card_border"),
        )
        self.donut_chart_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.donut_chart_card.grid_rowconfigure(1, weight=1)
        self.donut_chart_card.grid_columnconfigure(0, weight=1)

        pie_header_row = ctk.CTkFrame(self.donut_chart_card, fg_color="transparent")
        pie_header_row.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        pie_header_row.grid_columnconfigure(0, weight=1)

        self.donut_chart_title = ctk.CTkLabel(
            pie_header_row,
            text="Advanced Pie: Income Modes & Expenses",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=self._color("text_primary"),
        )
        self.donut_chart_title.grid(row=0, column=0, sticky="w")

        self.dash_pie_mode_var = ctk.StringVar(value="Income + Expense")
        self.dash_pie_mode_seg = ctk.CTkSegmentedButton(
            pie_header_row,
            values=["Income + Expense", "Income Modes", "Expenses"],
            variable=self.dash_pie_mode_var,
            command=lambda _v: self.draw_expense_donut_chart(),
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            selected_color="#6366f1",
            selected_hover_color="#4f46e5",
        )
        self.dash_pie_mode_seg.grid(row=0, column=1, sticky="e")

        self.donut_canvas_holder = ctk.CTkFrame(self.donut_chart_card, fg_color="transparent")
        self.donut_canvas_holder.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

    def build_recent_transactions_panel(self) -> None:
        """Build a bottom panel on Page 1 displaying recent transactions with ✎ Edit & ✕ Delete."""
        self.recent_card = ctk.CTkFrame(
            self.dashboard_page,
            height=180,
            corner_radius=14,
            fg_color=self._color("card_bg"),
            border_width=1,
            border_color=self._color("card_border"),
        )
        self.recent_card.grid(row=3, column=0, sticky="ew")
        self.recent_card.grid_propagate(False)
        self.recent_card.grid_columnconfigure(0, weight=1)
        self.recent_card.grid_rowconfigure(1, weight=1)

        self.recent_title = ctk.CTkLabel(
            self.recent_card,
            text="Recent Monthly Transactions — Click '✎ Edit' on any row to modify",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=self._color("text_primary"),
        )
        self.recent_title.grid(row=0, column=0, sticky="w", padx=18, pady=(10, 4))

        self.tx_scroll = ctk.CTkScrollableFrame(
            self.recent_card,
            fg_color="transparent",
            height=120,
        )
        self.tx_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.tx_scroll.grid_columnconfigure(3, weight=1)

    # -------------------------------------------------------------------------
    # PAGE 2: SEPARATE MONTHLY & WEEKLY ANALYTICS PAGE (WITH FULL EDIT & PIE)
    # -------------------------------------------------------------------------

    def build_analytics_page(self) -> None:
        """
        Build the separate Monthly & Weekly Data Explorer page with:
        - Period Mode selector (Weekly W1–W5 vs Monthly Comparison)
        - Specific Month & Week selector
        - Source filter ('All Data' vs 'My Inputs Only')
        - Advanced Pie Chart with 'Income + Expense', 'Income Modes', and 'Expenses'
        - Full Interactive Editable Table with '✎ Edit' and '✕ Delete' on every row
        """
        self.filter_card = ctk.CTkFrame(
            self.analytics_page,
            corner_radius=14,
            fg_color=self._color("card_bg"),
            border_width=1,
            border_color=self._color("card_border"),
        )
        self.filter_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.filter_card.grid_columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(self.filter_card, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew", padx=18, pady=(10, 6))
        top_row.grid_columnconfigure(0, weight=1)

        self.analytics_header_lbl = ctk.CTkLabel(
            top_row,
            text="Monthly & Weekly Data Explorer — Full Data Editor & Income Modes (₹)",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=self._color("text_primary"),
        )
        self.analytics_header_lbl.grid(row=0, column=0, sticky="w")

        back_btn = ctk.CTkButton(
            top_row,
            text="← Back to Overview Dashboard",
            command=lambda: self.switch_page("dashboard"),
            height=30,
            corner_radius=8,
            fg_color="#334155",
            hover_color="#475569",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        back_btn.grid(row=0, column=1, sticky="e")

        # Interactive Controls Row
        ctrl_row = ctk.CTkFrame(self.filter_card, fg_color="transparent")
        ctrl_row.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        mode_lbl = ctk.CTkLabel(
            ctrl_row,
            text="View Mode:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=self._color("text_secondary"),
        )
        mode_lbl.pack(side="left", padx=(0, 6))

        self.period_mode_var = ctk.StringVar(value="Weekly View")
        self.period_mode_seg = ctk.CTkSegmentedButton(
            ctrl_row,
            values=["Weekly View", "Monthly View"],
            variable=self.period_mode_var,
            command=lambda _v: self.refresh_analytics_page(),
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        self.period_mode_seg.pack(side="left", padx=(0, 14))

        m_lbl = ctk.CTkLabel(
            ctrl_row,
            text="Month:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=self._color("text_secondary"),
        )
        m_lbl.pack(side="left", padx=(0, 6))

        self.month_filter_var = ctk.StringVar(value=self.current_month)
        self.month_selector = ctk.CTkOptionMenu(
            ctrl_row,
            variable=self.month_filter_var,
            values=self.get_available_months(),
            command=lambda _v: self.refresh_analytics_page(),
            width=110,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.month_selector.pack(side="left", padx=(0, 14))

        w_lbl = ctk.CTkLabel(
            ctrl_row,
            text="Week Filter:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=self._color("text_secondary"),
        )
        w_lbl.pack(side="left", padx=(0, 6))

        week_options = ["All Weeks (Full Month)"] + [b[0] for b in WEEK_BUCKETS]
        self.week_filter_var = ctk.StringVar(value=week_options[0])
        self.week_selector = ctk.CTkOptionMenu(
            ctrl_row,
            variable=self.week_filter_var,
            values=week_options,
            command=lambda _v: self.refresh_analytics_page(),
            width=170,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.week_selector.pack(side="left", padx=(0, 14))

        src_lbl = ctk.CTkLabel(
            ctrl_row,
            text="Source:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=self._color("text_secondary"),
        )
        src_lbl.pack(side="left", padx=(0, 6))

        self.source_filter_var = ctk.StringVar(value="All Data")
        self.source_seg = ctk.CTkSegmentedButton(
            ctrl_row,
            values=["All Data", "My Inputs Only"],
            variable=self.source_filter_var,
            command=lambda _v: self.refresh_analytics_page(),
            height=30,
            selected_color="#10b981",
            selected_hover_color="#059669",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        self.source_seg.pack(side="left")

        # Row 1: Period Summary KPI Cards
        self.analytics_kpi_row = ctk.CTkFrame(self.analytics_page, fg_color="transparent")
        self.analytics_kpi_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for col in range(3):
            self.analytics_kpi_row.grid_columnconfigure(col, weight=1, uniform="akpi")

        self.akpi_inc_card, self.akpi_inc_val, self.akpi_inc_sub = self._create_kpi_card(
            parent=self.analytics_kpi_row,
            column=0,
            title="SELECTED PERIOD INCOME (₹)",
            accent_color=self._color("income"),
            padx=(0, 8),
        )
        self.akpi_exp_card, self.akpi_exp_val, self.akpi_exp_sub = self._create_kpi_card(
            parent=self.analytics_kpi_row,
            column=1,
            title="SELECTED PERIOD EXPENSES (₹)",
            accent_color=self._color("expense"),
            padx=(8, 8),
        )
        self.akpi_net_card, self.akpi_net_val, self.akpi_net_sub = self._create_kpi_card(
            parent=self.analytics_kpi_row,
            column=2,
            title="SELECTED PERIOD NET FLOW (₹)",
            accent_color=self._color("balance"),
            padx=(8, 0),
        )

        # Row 2: Weekly / Monthly Embedded Matplotlib Charts
        self.analytics_charts_row = ctk.CTkFrame(self.analytics_page, fg_color="transparent")
        self.analytics_charts_row.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        self.analytics_charts_row.grid_columnconfigure(0, weight=11)
        self.analytics_charts_row.grid_columnconfigure(1, weight=10)
        self.analytics_charts_row.grid_rowconfigure(0, weight=1)

        # Left Chart: Weekly (W1–W5) or Monthly Grouped Bar Comparison
        self.bar_chart_card = ctk.CTkFrame(
            self.analytics_charts_row,
            corner_radius=14,
            fg_color=self._color("card_bg"),
            border_width=1,
            border_color=self._color("card_border"),
        )
        self.bar_chart_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.bar_chart_card.grid_rowconfigure(1, weight=1)
        self.bar_chart_card.grid_columnconfigure(0, weight=1)

        self.bar_chart_title = ctk.CTkLabel(
            self.bar_chart_card,
            text="Weekly Breakdown (Week 1 to Week 5) — Income vs. Expenses (₹)",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=self._color("text_primary"),
        )
        self.bar_chart_title.grid(row=0, column=0, sticky="w", padx=18, pady=(10, 2))

        self.bar_canvas_holder = ctk.CTkFrame(self.bar_chart_card, fg_color="transparent")
        self.bar_canvas_holder.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        # Right Chart: Advanced Pie Chart on Page 2 (Income + Expense / Income Modes / Expenses)
        self.analytics_cat_card = ctk.CTkFrame(
            self.analytics_charts_row,
            corner_radius=14,
            fg_color=self._color("card_bg"),
            border_width=1,
            border_color=self._color("card_border"),
        )
        self.analytics_cat_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.analytics_cat_card.grid_rowconfigure(1, weight=1)
        self.analytics_cat_card.grid_columnconfigure(0, weight=1)

        p2_pie_header = ctk.CTkFrame(self.analytics_cat_card, fg_color="transparent")
        p2_pie_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 2))
        p2_pie_header.grid_columnconfigure(0, weight=1)

        self.analytics_cat_title = ctk.CTkLabel(
            p2_pie_header,
            text="Advanced Pie Breakdown (₹)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=self._color("text_primary"),
        )
        self.analytics_cat_title.grid(row=0, column=0, sticky="w")

        self.analytics_pie_mode_var = ctk.StringVar(value="Income + Expense")
        self.analytics_pie_mode_seg = ctk.CTkSegmentedButton(
            p2_pie_header,
            values=["Income + Expense", "Income Modes", "Expenses"],
            variable=self.analytics_pie_mode_var,
            command=lambda _v: self.refresh_analytics_page(),
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            selected_color="#6366f1",
            selected_hover_color="#4f46e5",
        )
        self.analytics_pie_mode_seg.grid(row=0, column=1, sticky="e")

        self.analytics_cat_canvas_holder = ctk.CTkFrame(
            self.analytics_cat_card,
            fg_color="transparent",
        )
        self.analytics_cat_canvas_holder.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Row 3: Interactive Weekly/Monthly Transactions Table (With ✎ Edit & ✕ Delete)
        self.analytics_table_card = ctk.CTkFrame(
            self.analytics_page,
            height=215,
            corner_radius=14,
            fg_color=self._color("card_bg"),
            border_width=1,
            border_color=self._color("card_border"),
        )
        self.analytics_table_card.grid(row=3, column=0, sticky="nsew")
        self.analytics_table_card.grid_columnconfigure(0, weight=1)
        self.analytics_table_card.grid_rowconfigure(1, weight=1)

        self.analytics_table_title = ctk.CTkLabel(
            self.analytics_table_card,
            text="All Matching Transactions — Click '✎ Edit' to load into Left Form or Quick-Edit",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=self._color("text_primary"),
        )
        self.analytics_table_title.grid(row=0, column=0, sticky="w", padx=18, pady=(10, 4))

        self.analytics_tx_scroll = ctk.CTkScrollableFrame(
            self.analytics_table_card,
            fg_color="transparent",
            height=155,
        )
        self.analytics_tx_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.analytics_tx_scroll.grid_columnconfigure(4, weight=1)

    def switch_page(self, page_name: str) -> None:
        """Switch between 'dashboard' (Page 1) and 'analytics' (Page 2)."""
        self.active_page = page_name
        if page_name == "dashboard":
            self.dashboard_page.tkraise()
            self.nav_dash_btn.configure(fg_color=self._color("nav_active"), text_color="#ffffff")
            self.nav_analytics_btn.configure(
                fg_color=self._color("nav_inactive"),
                text_color=self._color("text_primary"),
            )
            self.refresh_dashboard()
        else:
            self.analytics_page.tkraise()
            self.nav_analytics_btn.configure(fg_color=self._color("nav_active"), text_color="#ffffff")
            self.nav_dash_btn.configure(
                fg_color=self._color("nav_inactive"),
                text_color=self._color("text_primary"),
            )
            self.refresh_analytics_page()

    # =========================================================================
    # 3. MATPLOTLIB EMBEDDED CHARTING (ADVANCED PIE WITH INCOME MODES)
    # =========================================================================

    def init_matplotlib_canvases(self) -> None:
        """Create Matplotlib Figure objects and embed them into both pages."""
        card_bg = self._color("card_bg")

        # Page 1: Line Chart Figure & Canvas
        self.line_fig = Figure(figsize=(5.8, 3.3), dpi=100, facecolor=card_bg)
        self.line_canvas = FigureCanvasTkAgg(self.line_fig, master=self.line_canvas_holder)
        self.line_canvas_widget = self.line_canvas.get_tk_widget()
        self.line_canvas_widget.configure(bg=card_bg, highlightthickness=0)
        self.line_canvas_widget.pack(fill="both", expand=True)

        # Page 1: Advanced Multi-Mode Pie Chart Figure & Canvas
        self.donut_fig = Figure(figsize=(5.2, 3.3), dpi=100, facecolor=card_bg)
        self.donut_canvas = FigureCanvasTkAgg(self.donut_fig, master=self.donut_canvas_holder)
        self.donut_canvas_widget = self.donut_canvas.get_tk_widget()
        self.donut_canvas_widget.configure(bg=card_bg, highlightthickness=0)
        self.donut_canvas_widget.pack(fill="both", expand=True)

        # Page 2: Weekly/Monthly Grouped Bar Chart Figure & Canvas
        self.bar_fig = Figure(figsize=(5.8, 2.7), dpi=100, facecolor=card_bg)
        self.bar_canvas = FigureCanvasTkAgg(self.bar_fig, master=self.bar_canvas_holder)
        self.bar_canvas_widget = self.bar_canvas.get_tk_widget()
        self.bar_canvas_widget.configure(bg=card_bg, highlightthickness=0)
        self.bar_canvas_widget.pack(fill="both", expand=True)

        # Page 2: Advanced Multi-Mode Pie Chart Figure & Canvas
        self.analytics_cat_fig = Figure(figsize=(5.2, 2.7), dpi=100, facecolor=card_bg)
        self.analytics_cat_canvas = FigureCanvasTkAgg(
            self.analytics_cat_fig,
            master=self.analytics_cat_canvas_holder,
        )
        self.analytics_cat_widget = self.analytics_cat_canvas.get_tk_widget()
        self.analytics_cat_widget.configure(bg=card_bg, highlightthickness=0)
        self.analytics_cat_widget.pack(fill="both", expand=True)

    def render_charts(self) -> None:
        """Redraw Page 1 embedded Matplotlib charts using the latest SQLite data."""
        self.draw_income_expense_line_chart()
        self.draw_expense_donut_chart()

    def draw_income_expense_line_chart(self) -> None:
        """
        Render the embedded Matplotlib line chart comparing cumulative Income vs. Expenses
        in INR (₹) over the days of the active month.
        """
        card_bg = self._color("card_bg")
        text_primary = self._color("text_primary")
        text_secondary = self._color("text_secondary")
        grid_color = self._color("grid_line")
        inc_color = self._color("income")
        exp_color = self._color("expense")

        days, inc_disc, exp_disc, inc_cum, exp_cum = self.fetch_daily_series(self.current_month)

        self.line_fig.clear()
        self.line_fig.patch.set_facecolor(card_bg)
        self.line_canvas_widget.configure(bg=card_bg)

        ax = self.line_fig.add_subplot(111)
        ax.set_facecolor(card_bg)

        ax.plot(
            days,
            inc_cum,
            label="Cumulative Income (₹)",
            color=inc_color,
            linewidth=2.5,
            zorder=4,
        )
        ax.fill_between(days, inc_cum, color=inc_color, alpha=0.14, zorder=2)

        ax.plot(
            days,
            exp_cum,
            label="Cumulative Expenses (₹)",
            color=exp_color,
            linewidth=2.5,
            zorder=4,
        )
        ax.fill_between(days, exp_cum, color=exp_color, alpha=0.14, zorder=2)

        inc_active_days = [d for d, val in zip(days, inc_disc) if val > 0]
        inc_active_vals = [cum for val, cum in zip(inc_disc, inc_cum) if val > 0]
        if inc_active_days:
            ax.scatter(
                inc_active_days,
                inc_active_vals,
                color=inc_color,
                s=34,
                edgecolors=card_bg,
                linewidths=1.2,
                zorder=5,
            )

        exp_active_days = [d for d, val in zip(days, exp_disc) if val > 0]
        exp_active_vals = [cum for val, cum in zip(exp_disc, exp_cum) if val > 0]
        if exp_active_days:
            ax.scatter(
                exp_active_days,
                exp_active_vals,
                color=exp_color,
                s=34,
                edgecolors=card_bg,
                linewidths=1.2,
                zorder=5,
            )

        ax.set_xlim(1, len(days))
        max_y = max(max(inc_cum, default=0.0), max(exp_cum, default=0.0), 1000.0)
        ax.set_ylim(0, max_y * 1.15)

        ax.set_xlabel("Day of Month", color=text_secondary, fontsize=9, labelpad=6)
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda x, _pos: format_inr(x, include_decimals=False))
        )

        ax.grid(True, linestyle="--", linewidth=0.7, color=grid_color, alpha=0.65)
        ax.tick_params(axis="both", colors=text_secondary, labelsize=8.5)

        for spine_name, spine in ax.spines.items():
            if spine_name in ("top", "right"):
                spine.set_visible(False)
            else:
                spine.set_color(grid_color)

        legend = ax.legend(
            loc="upper left",
            frameon=True,
            facecolor=card_bg,
            edgecolor=grid_color,
            fontsize=8.5,
        )
        for text in legend.get_texts():
            text.set_color(text_primary)

        self.line_fig.tight_layout(pad=1.2)
        self.line_canvas.draw_idle()

    def draw_expense_donut_chart(self) -> None:
        """
        Render the Page 1 Advanced Pie/Donut Chart supporting:
        - 'Income + Expense' (Dual side-by-side Income Modes & Expense Categories rings)
        - 'Income Modes' (Detailed exploded Pie/Donut of Income sources in ₹)
        - 'Expenses' (Detailed exploded Pie/Donut of Expense categories in ₹)
        """
        mode = self.dash_pie_mode_var.get()
        inc_breakdown = self.fetch_category_breakdown("Income", month_str=self.current_month)
        exp_breakdown = self.fetch_category_breakdown("Expense", month_str=self.current_month)

        self._render_advanced_pie_figure(
            fig=self.donut_fig,
            canvas=self.donut_canvas,
            widget=self.donut_canvas_widget,
            mode=mode,
            inc_breakdown=inc_breakdown,
            exp_breakdown=exp_breakdown,
        )

    def _render_advanced_pie_figure(
        self,
        fig: Figure,
        canvas: FigureCanvasTkAgg,
        widget: object,
        mode: str,
        inc_breakdown: List[Tuple[str, float]],
        exp_breakdown: List[Tuple[str, float]],
    ) -> None:
        """
        Render an advanced Matplotlib pie/donut visualization on `fig`:
        - If mode == 'Income + Expense': Dual side-by-side donut charts showing both
          Income Modes (left ring) and Expense Categories (right ring) with center totals
          and individual legends.
        - If mode == 'Income Modes': Full-size exploded donut chart of Income Modes with
          percentage shares, ₹ values, and center Total Income readout.
        - If mode == 'Expenses': Full-size exploded donut chart of Expense Categories with
          percentage shares, ₹ values, and center Total Spend readout.
        """
        card_bg = self._color("card_bg")
        text_primary = self._color("text_primary")
        text_secondary = self._color("text_secondary")

        fig.clear()
        fig.patch.set_facecolor(card_bg)
        if hasattr(widget, "configure"):
            widget.configure(bg=card_bg)

        if mode == "Income + Expense":
            ax_inc = fig.add_subplot(121)
            ax_exp = fig.add_subplot(122)
            ax_inc.set_facecolor(card_bg)
            ax_exp.set_facecolor(card_bg)

            self._draw_single_donut_subplot(
                ax=ax_inc,
                breakdown=inc_breakdown,
                palette=INCOME_PIE_COLORS,
                center_title="Income Modes",
                empty_msg="No Income\nRecorded",
                card_bg=card_bg,
                text_primary=text_primary,
                text_secondary=text_secondary,
                compact=True,
            )
            self._draw_single_donut_subplot(
                ax=ax_exp,
                breakdown=exp_breakdown,
                palette=EXPENSE_PIE_COLORS,
                center_title="Expenses",
                empty_msg="No Expenses\nRecorded",
                card_bg=card_bg,
                text_primary=text_primary,
                text_secondary=text_secondary,
                compact=True,
            )
            fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.25, wspace=0.18)
            canvas.draw_idle()
            return

        # Single full-size Advanced Exploded Pie/Donut Mode ('Income Modes' or 'Expenses')
        ax = fig.add_subplot(111)
        ax.set_facecolor(card_bg)

        if mode == "Income Modes":
            self._draw_single_donut_subplot(
                ax=ax,
                breakdown=inc_breakdown,
                palette=INCOME_PIE_COLORS,
                center_title="Total Income",
                empty_msg="No income modes recorded\nfor this selection",
                card_bg=card_bg,
                text_primary=text_primary,
                text_secondary=text_secondary,
                compact=False,
            )
        else:
            self._draw_single_donut_subplot(
                ax=ax,
                breakdown=exp_breakdown,
                palette=EXPENSE_PIE_COLORS,
                center_title="Total Spend",
                empty_msg="No expenses recorded\nfor this selection",
                card_bg=card_bg,
                text_primary=text_primary,
                text_secondary=text_secondary,
                compact=False,
            )

        fig.subplots_adjust(left=0.04, right=0.96, top=0.94, bottom=0.24)
        canvas.draw_idle()

    def _draw_single_donut_subplot(
        self,
        ax: object,
        breakdown: List[Tuple[str, float]],
        palette: List[str],
        center_title: str,
        empty_msg: str,
        card_bg: str,
        text_primary: str,
        text_secondary: str,
        compact: bool = False,
    ) -> None:
        """Draw an exploded donut chart with center ₹ readout and legend on a Matplotlib Axes."""
        if not breakdown:
            ax.text(
                0.5,
                0.5,
                empty_msg,
                ha="center",
                va="center",
                color=text_secondary,
                fontsize=9.5 if compact else 10.5,
            )
            ax.axis("off")
            return

        categories = [item[0] for item in breakdown]
        amounts = [item[1] for item in breakdown]
        total_val = sum(amounts)
        colors = [palette[i % len(palette)] for i in range(len(categories))]

        # Slightly explode the largest mode/category slice for visual emphasis
        explode = [0.05 if i == 0 and len(categories) > 1 else 0.0 for i in range(len(categories))]

        wedges, _texts, autotexts = ax.pie(
            amounts,
            explode=explode,
            labels=None,
            autopct=lambda pct: f"{pct:.0f}%" if pct >= 7.0 else "",
            pctdistance=0.76,
            startangle=135,
            colors=colors,
            wedgeprops={"width": 0.44, "edgecolor": card_bg, "linewidth": 2.0},
        )

        for autotext in autotexts:
            autotext.set_color("#ffffff")
            autotext.set_fontsize(7.5 if compact else 8.5)
            autotext.set_fontweight("bold")

        ax.text(
            0,
            0.10,
            center_title,
            ha="center",
            va="center",
            fontsize=8 if compact else 9,
            fontweight="bold",
            color=text_secondary,
        )
        ax.text(
            0,
            -0.12,
            format_inr(total_val, include_decimals=False),
            ha="center",
            va="center",
            fontsize=9.5 if compact else 12,
            fontweight="bold",
            color=text_primary,
        )

        ax.axis("equal")

        max_items = 4 if compact else 8
        legend_labels = []
        for cat, amt in zip(categories[:max_items], amounts[:max_items]):
            pct = (amt / total_val * 100.0) if total_val > 0 else 0.0
            short_cat = cat[:13] + "…" if (compact and len(cat) > 14) else cat[:18]
            if compact:
                legend_labels.append(f"{short_cat} ({pct:.0f}%)")
            else:
                legend_labels.append(f"{short_cat}: {format_inr(amt, False)} ({pct:.0f}%)")

        legend = ax.legend(
            wedges[:max_items],
            legend_labels,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.32 if compact else -0.26),
            ncol=1 if compact else 2,
            frameon=False,
            fontsize=7.2 if compact else 7.8,
        )
        for text in legend.get_texts():
            text.set_color(text_secondary)

    def draw_analytics_charts(
        self,
        target_ym: str,
        only_user_input: bool,
        week_num: Optional[int],
        is_monthly_mode: bool,
    ) -> None:
        """
        Draw the Weekly (Week 1–5) or Monthly comparison bar chart and the
        Advanced Multi-Mode Pie Chart on Page 2.
        """
        card_bg = self._color("card_bg")
        text_primary = self._color("text_primary")
        text_secondary = self._color("text_secondary")
        grid_color = self._color("grid_line")
        inc_color = self._color("income")
        exp_color = self._color("expense")

        if is_monthly_mode:
            labels, inc_vals, exp_vals = self.fetch_monthly_comparison_series(only_user_input)
            self.bar_chart_title.configure(
                text="Monthly Comparison — Income vs. Expenses (₹)"
            )
        else:
            labels, inc_vals, exp_vals = self.fetch_weekly_series(target_ym, only_user_input)
            self.bar_chart_title.configure(
                text=f"Weekly Breakdown ({target_ym}: Week 1 to Week 5) — Income vs. Expenses (₹)"
            )

        self.bar_fig.clear()
        self.bar_fig.patch.set_facecolor(card_bg)
        self.bar_canvas_widget.configure(bg=card_bg)

        ax = self.bar_fig.add_subplot(111)
        ax.set_facecolor(card_bg)

        x_positions = list(range(len(labels)))
        bar_width = 0.34

        inc_positions = [x - bar_width / 2 for x in x_positions]
        exp_positions = [x + bar_width / 2 for x in x_positions]

        ax.bar(
            inc_positions,
            inc_vals,
            width=bar_width,
            label="Income (₹)",
            color=inc_color,
            zorder=3,
        )
        ax.bar(
            exp_positions,
            exp_vals,
            width=bar_width,
            label="Expenses (₹)",
            color=exp_color,
            zorder=3,
        )

        if not is_monthly_mode and week_num is not None and 1 <= week_num <= len(x_positions):
            ax.axvspan(
                week_num - 1 - 0.45,
                week_num - 1 + 0.45,
                color="#38bdf8",
                alpha=0.14,
                zorder=1,
            )

        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels, color=text_secondary, fontsize=8.5)
        max_bar = max(max(inc_vals, default=0.0), max(exp_vals, default=0.0), 1000.0)
        ax.set_ylim(0, max_bar * 1.2)
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda x, _pos: format_inr(x, include_decimals=False))
        )

        ax.grid(
            True,
            axis="y",
            linestyle="--",
            linewidth=0.7,
            color=grid_color,
            alpha=0.65,
            zorder=0,
        )
        ax.tick_params(axis="y", colors=text_secondary, labelsize=8.5)

        for spine_name, spine in ax.spines.items():
            if spine_name in ("top", "right"):
                spine.set_visible(False)
            else:
                spine.set_color(grid_color)

        legend = ax.legend(
            loc="upper right",
            frameon=True,
            facecolor=card_bg,
            edgecolor=grid_color,
            fontsize=8.5,
        )
        for text in legend.get_texts():
            text.set_color(text_primary)

        self.bar_fig.tight_layout(pad=1.0)
        self.bar_canvas.draw_idle()

        # Right Chart on Page 2: Advanced Pie Chart (Income + Expense / Income Modes / Expenses)
        eff_week = week_num if not is_monthly_mode else None
        inc_breakdown = self.fetch_category_breakdown(
            tx_type="Income",
            month_str=target_ym,
            only_user_input=only_user_input,
            week_num=eff_week,
        )
        exp_breakdown = self.fetch_category_breakdown(
            tx_type="Expense",
            month_str=target_ym,
            only_user_input=only_user_input,
            week_num=eff_week,
        )
        self._render_advanced_pie_figure(
            fig=self.analytics_cat_fig,
            canvas=self.analytics_cat_canvas,
            widget=self.analytics_cat_widget,
            mode=self.analytics_pie_mode_var.get(),
            inc_breakdown=inc_breakdown,
            exp_breakdown=exp_breakdown,
        )

    # =========================================================================
    # 4. EVENT HANDLERS, FULL EDIT MODE & LIVE UI REFRESH
    # =========================================================================

    def on_transaction_type_change(self, selected_type: str) -> None:
        """Update category/mode dropdown options and label when switching Income/Expense."""
        if selected_type == "Income":
            self.category_field_label.configure(text="INCOME MODE (OR TYPE CUSTOM)")
            self.category_combobox.configure(values=INCOME_CATEGORIES)
            if self.category_combobox.get() not in INCOME_CATEGORIES:
                self.category_combobox.set(INCOME_CATEGORIES[0])
            self.tx_type_selector.configure(
                selected_color="#10b981",
                selected_hover_color="#059669",
            )
        else:
            self.category_field_label.configure(text="EXPENSE CATEGORY (OR TYPE CUSTOM)")
            self.category_combobox.configure(values=EXPENSE_CATEGORIES)
            if self.category_combobox.get() not in EXPENSE_CATEGORIES:
                self.category_combobox.set(EXPENSE_CATEGORIES[0])
            self.tx_type_selector.configure(
                selected_color="#f43f5e",
                selected_hover_color="#e11d48",
            )

    def start_edit_transaction(self, tx_id: int) -> None:
        """
        Load any existing transaction (#tx_id) into the left sidebar form so the user
        has full access to edit its Type, Date, Amount (₹), Income Mode / Category, and Note.
        """
        row = self.fetch_transaction_by_id(tx_id)
        if row is None:
            self._set_status(f"Transaction #{tx_id} not found.", is_error=True)
            return

        self.editing_tx_id = int(row["id"])
        tx_type = str(row["tx_type"])
        tx_date = str(row["tx_date"])
        amount = float(row["amount"])
        category = str(row["category"])
        note = str(row["note"]) if row["note"] else ""

        # Populate form fields
        self.tx_type_var.set(tx_type)
        self.on_transaction_type_change(tx_type)

        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, tx_date)

        self.amount_entry.delete(0, "end")
        self.amount_entry.insert(0, f"{amount:.2f}")

        self.category_combobox.set(category)

        self.note_entry.delete(0, "end")
        self.note_entry.insert(0, note)

        # Highlight form in Edit Mode
        self.form_header_lbl.configure(
            text=f"✎ Editing Entry #{self.editing_tx_id} (₹)",
            text_color=self._color("edit_accent"),
        )
        self.form_card.configure(border_color=self._color("edit_accent"), border_width=2)
        self.submit_btn.configure(
            text=f"✓ Update #{self.editing_tx_id}",
            fg_color="#d97706",
            hover_color="#b45309",
        )
        self.cancel_edit_btn.grid(row=0, column=1, padx=(6, 0))
        self.amount_entry.focus_set()

        self._set_status(
            f"Editing #{self.editing_tx_id}: Modify fields above and click '✓ Update'.",
            is_error=False,
        )

    def cancel_edit_mode(self) -> None:
        """Exit edit mode and restore the sidebar form to 'Add New Entry' mode."""
        self.editing_tx_id = None
        self.form_header_lbl.configure(
            text="Add New Entry (₹ INR)",
            text_color=self._color("text_primary"),
        )
        self.form_card.configure(border_color=self._color("card_border"), border_width=1)
        self.submit_btn.configure(
            text="+ Save Entry (₹)",
            fg_color="#3b82f6",
            hover_color="#2563eb",
        )
        self.cancel_edit_btn.grid_forget()

        self.amount_entry.delete(0, "end")
        self.note_entry.delete(0, "end")
        self._set_status("Edit cancelled. Ready to add new entries.", is_error=False)

    def handle_save_or_update_transaction(self) -> None:
        """
        Validate form fields and either INSERT a new transaction or UPDATE the
        currently edited transaction (`self.editing_tx_id`) in SQLite.
        """
        tx_type = self.tx_type_var.get().strip()
        tx_date = self.date_entry.get().strip()
        raw_amount = (
            self.amount_entry.get()
            .strip()
            .replace(",", "")
            .replace("₹", "")
            .replace("$", "")
        )
        category = self.category_combobox.get().strip()
        note = self.note_entry.get().strip()

        try:
            parsed_date = datetime.strptime(tx_date, "%Y-%m-%d")
            normalized_date = parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            self._set_status("Invalid date. Use YYYY-MM-DD format.", is_error=True)
            return

        try:
            amount = float(raw_amount)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            self._set_status("Enter a valid positive ₹ amount (e.g. 1500).", is_error=True)
            return

        if not category:
            self._set_status("Please select or enter a category / income mode.", is_error=True)
            return

        week_num = day_to_week_number(parsed_date.day)

        if self.editing_tx_id is not None:
            edited_id = self.editing_tx_id
            self.update_transaction(
                tx_id=edited_id,
                tx_date=normalized_date,
                tx_type=tx_type,
                category=category,
                amount=amount,
                note=note,
            )
            self.cancel_edit_mode()
            self._set_status(
                f"Updated #{edited_id}: {tx_type} {format_inr(amount)} in {category} (W{week_num})",
                is_error=False,
            )
        else:
            self.insert_transaction(
                tx_date=normalized_date,
                tx_type=tx_type,
                category=category,
                amount=amount,
                note=note,
                is_mock=0,
            )
            self.amount_entry.delete(0, "end")
            self.note_entry.delete(0, "end")
            self._set_status(
                f"Saved {tx_type}: {format_inr(amount)} in {category} (Week {week_num})",
                is_error=False,
            )

        logged_month = normalized_date[:7]
        self.current_month = logged_month
        self.month_selector.configure(values=self.get_available_months())
        self.month_filter_var.set(logged_month)

        month_pretty = datetime.strptime(self.current_month, "%Y-%m").strftime("%B %Y")
        self.dashboard_title.configure(
            text=f"Monthly Financial Dashboard (INR ₹) — {month_pretty}"
        )

        self.refresh_all_views()

    def handle_delete_transaction(self, tx_id: int) -> None:
        """Delete a transaction row and refresh both pages."""
        if self.editing_tx_id == tx_id:
            self.cancel_edit_mode()
        self.delete_transaction(tx_id)
        self._set_status(f"Deleted transaction #{tx_id}.", is_error=False)
        self.refresh_all_views()

    def handle_reset_mock_data(self) -> None:
        """Re-seed the current month with fresh INR mock data while keeping user inputs."""
        self.cancel_edit_mode()
        self.current_month = datetime.now().strftime("%Y-%m")
        inserted = populate_mock_data(self.db_path, self.current_month, force=True)
        self.month_selector.configure(values=self.get_available_months())
        self.month_filter_var.set(self.current_month)
        self.source_filter_var.set("All Data")
        self._set_status(
            f"Seeded {inserted} INR (₹) mock entries for {self.current_month}.",
            is_error=False,
        )
        self.refresh_all_views()

    def handle_clear_mock_data(self) -> None:
        """Remove all mock records so only user-entered inputs remain."""
        self.cancel_edit_mode()
        removed = self.clear_mock_transactions()
        self.source_filter_var.set("My Inputs Only")
        self._set_status(
            f"Cleared {removed} mock entries. Showing only your inputs!",
            is_error=False,
        )
        self.refresh_all_views()

    def refresh_all_views(self) -> None:
        """Refresh both the primary Overview Dashboard and the Weekly & Monthly Explorer."""
        self.refresh_dashboard()
        self.refresh_analytics_page()

    def refresh_dashboard(self) -> None:
        """Synchronize Page 1 KPI cards, embedded Matplotlib charts, and recent transaction feed."""
        summary = self.fetch_monthly_summary(self.current_month)
        income = summary["income"]
        expense = summary["expense"]
        net = summary["net_balance"]
        inc_count = int(summary["income_count"])
        exp_count = int(summary["expense_count"])

        self.income_val_lbl.configure(
            text=format_inr(income),
            text_color=self._color("income"),
        )
        self.income_sub_lbl.configure(
            text=f"{inc_count} income {'entry' if inc_count == 1 else 'entries'} this month"
        )

        self.expense_val_lbl.configure(
            text=format_inr(expense),
            text_color=self._color("expense"),
        )
        self.expense_sub_lbl.configure(
            text=f"{exp_count} expense {'entry' if exp_count == 1 else 'entries'} this month"
        )

        sign_prefix = "+" if net >= 0 else "-"
        balance_color = self._color("income") if net >= 0 else self._color("expense")
        savings_rate = ((net / income) * 100.0) if income > 0 else 0.0
        self.balance_val_lbl.configure(
            text=f"{sign_prefix}{format_inr(abs(net))}",
            text_color=balance_color,
        )
        self.balance_sub_lbl.configure(
            text=f"Savings rate: {savings_rate:.1f}% of monthly income"
        )

        self.render_charts()
        self._populate_recent_transactions_list()

    def _selected_week_number(self) -> Optional[int]:
        """Parse the currently selected week number (1..5) or None for All Weeks."""
        raw = self.week_filter_var.get()
        for idx, (label, _s, _e) in enumerate(WEEK_BUCKETS, start=1):
            if raw == label:
                return idx
        return None

    def refresh_analytics_page(self) -> None:
        """Refresh Page 2 (Weekly & Monthly Explorer) KPIs, charts, and transaction table."""
        target_ym = self.month_filter_var.get() or self.current_month
        only_user_input = self.source_filter_var.get() == "My Inputs Only"
        is_monthly_mode = self.period_mode_var.get() == "Monthly View"
        week_num = None if is_monthly_mode else self._selected_week_number()

        summary = self.fetch_monthly_summary(
            month_str=target_ym,
            only_user_input=only_user_input,
            week_num=week_num,
        )
        inc = summary["income"]
        exp = summary["expense"]
        net = summary["net_balance"]
        inc_c = int(summary["income_count"])
        exp_c = int(summary["expense_count"])

        period_desc = (
            f"{target_ym} (Full Month)"
            if week_num is None
            else f"{target_ym} • Week {week_num}"
        )
        source_desc = "My Inputs Only" if only_user_input else "All Data"

        self.akpi_inc_val.configure(text=format_inr(inc), text_color=self._color("income"))
        self.akpi_inc_sub.configure(text=f"{inc_c} entries • {period_desc} ({source_desc})")

        self.akpi_exp_val.configure(text=format_inr(exp), text_color=self._color("expense"))
        self.akpi_exp_sub.configure(text=f"{exp_c} entries • {period_desc} ({source_desc})")

        sign_prefix = "+" if net >= 0 else "-"
        net_color = self._color("income") if net >= 0 else self._color("expense")
        self.akpi_net_val.configure(
            text=f"{sign_prefix}{format_inr(abs(net))}",
            text_color=net_color,
        )
        self.akpi_net_sub.configure(text=f"Net flow for {period_desc}")

        self.draw_analytics_charts(
            target_ym=target_ym,
            only_user_input=only_user_input,
            week_num=week_num,
            is_monthly_mode=is_monthly_mode,
        )
        self._populate_analytics_table(
            target_ym=target_ym,
            only_user_input=only_user_input,
            week_num=week_num,
        )

    def _populate_recent_transactions_list(self) -> None:
        """Render recent transaction rows on Page 1 with ✎ Edit and ✕ Delete buttons."""
        for child in self.tx_scroll.winfo_children():
            child.destroy()

        rows = self.fetch_filtered_transactions(month_str=self.current_month, limit=15)
        if not rows:
            empty_lbl = ctk.CTkLabel(
                self.tx_scroll,
                text="No transactions recorded for this month yet.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=self._color("text_secondary"),
            )
            empty_lbl.grid(row=0, column=0, padx=10, pady=10, sticky="w")
            return

        for idx, row in enumerate(rows):
            tx_id = int(row["id"])
            is_income = row["tx_type"] == "Income"
            badge_color = self._color("income") if is_income else self._color("expense")
            sign = "+" if is_income else "-"
            day_num = int(str(row["tx_date"])[8:10])
            week_num = day_to_week_number(day_num)
            source_tag = "My Input" if int(row["is_mock"]) == 0 else "Mock"

            date_lbl = ctk.CTkLabel(
                self.tx_scroll,
                text=f"{row['tx_date']} (W{week_num})",
                font=ctk.CTkFont(family="Consolas", size=12),
                text_color=self._color("text_secondary"),
                width=120,
                anchor="w",
            )
            date_lbl.grid(row=idx, column=0, padx=(6, 6), pady=2, sticky="w")

            src_lbl = ctk.CTkLabel(
                self.tx_scroll,
                text=f"[{source_tag}]",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#38bdf8" if source_tag == "My Input" else self._color("text_secondary"),
                width=72,
                anchor="w",
            )
            src_lbl.grid(row=idx, column=1, padx=4, pady=2, sticky="w")

            cat_lbl = ctk.CTkLabel(
                self.tx_scroll,
                text=f"{row['tx_type']} • {row['category']}",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=self._color("text_primary"),
                width=225,
                anchor="w",
            )
            cat_lbl.grid(row=idx, column=2, padx=6, pady=2, sticky="w")

            note_text = str(row["note"]) if row["note"] else "—"
            note_lbl = ctk.CTkLabel(
                self.tx_scroll,
                text=note_text,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=self._color("text_secondary"),
                anchor="w",
            )
            note_lbl.grid(row=idx, column=3, padx=6, pady=2, sticky="ew")

            amt_lbl = ctk.CTkLabel(
                self.tx_scroll,
                text=f"{sign}{format_inr(float(row['amount']))}",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=badge_color,
                width=120,
                anchor="e",
            )
            amt_lbl.grid(row=idx, column=4, padx=(6, 6), pady=2, sticky="e")

            edit_btn = ctk.CTkButton(
                self.tx_scroll,
                text="✎ Edit",
                width=54,
                height=24,
                corner_radius=6,
                fg_color="#334155",
                hover_color="#d97706",
                text_color="#f8fafc",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=lambda tid=tx_id: self.start_edit_transaction(tid),
            )
            edit_btn.grid(row=idx, column=5, padx=3, pady=2, sticky="e")

            del_btn = ctk.CTkButton(
                self.tx_scroll,
                text="✕",
                width=26,
                height=24,
                corner_radius=6,
                fg_color="transparent",
                hover_color="#e11d48",
                text_color=self._color("text_secondary"),
                command=lambda tid=tx_id: self.handle_delete_transaction(tid),
            )
            del_btn.grid(row=idx, column=6, padx=(2, 6), pady=2, sticky="e")

    def _populate_analytics_table(
        self,
        target_ym: str,
        only_user_input: bool,
        week_num: Optional[int],
    ) -> None:
        """Populate the Page 2 interactive transaction list with ✎ Edit and ✕ Delete buttons."""
        for child in self.analytics_tx_scroll.winfo_children():
            child.destroy()

        rows = self.fetch_filtered_transactions(
            month_str=target_ym,
            only_user_input=only_user_input,
            week_num=week_num,
            limit=100,
        )

        if not rows:
            msg = (
                "No user-entered transactions found for this filter yet. Add or Edit one using the left form!"
                if only_user_input
                else "No transactions match the selected Month/Week filter."
            )
            empty_lbl = ctk.CTkLabel(
                self.analytics_tx_scroll,
                text=msg,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=self._color("text_secondary"),
            )
            empty_lbl.grid(row=0, column=0, padx=10, pady=12, sticky="w")
            return

        for idx, row in enumerate(rows):
            tx_id = int(row["id"])
            is_income = row["tx_type"] == "Income"
            badge_color = self._color("income") if is_income else self._color("expense")
            sign = "+" if is_income else "-"
            day_num = int(str(row["tx_date"])[8:10])
            w_num = day_to_week_number(day_num)
            is_user = int(row["is_mock"]) == 0

            date_lbl = ctk.CTkLabel(
                self.analytics_tx_scroll,
                text=str(row["tx_date"]),
                font=ctk.CTkFont(family="Consolas", size=12),
                text_color=self._color("text_secondary"),
                width=90,
                anchor="w",
            )
            date_lbl.grid(row=idx, column=0, padx=(6, 4), pady=2, sticky="w")

            week_lbl = ctk.CTkLabel(
                self.analytics_tx_scroll,
                text=f"Week {w_num}",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#38bdf8",
                width=62,
                anchor="w",
            )
            week_lbl.grid(row=idx, column=1, padx=4, pady=2, sticky="w")

            src_lbl = ctk.CTkLabel(
                self.analytics_tx_scroll,
                text="[My Input]" if is_user else "[Mock]",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#10b981" if is_user else self._color("text_secondary"),
                width=74,
                anchor="w",
            )
            src_lbl.grid(row=idx, column=2, padx=4, pady=2, sticky="w")

            cat_lbl = ctk.CTkLabel(
                self.analytics_tx_scroll,
                text=f"{row['tx_type']} • {row['category']}",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=self._color("text_primary"),
                width=225,
                anchor="w",
            )
            cat_lbl.grid(row=idx, column=3, padx=6, pady=2, sticky="w")

            note_text = str(row["note"]) if row["note"] else "—"
            note_lbl = ctk.CTkLabel(
                self.analytics_tx_scroll,
                text=note_text,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=self._color("text_secondary"),
                anchor="w",
            )
            note_lbl.grid(row=idx, column=4, padx=6, pady=2, sticky="ew")

            amt_lbl = ctk.CTkLabel(
                self.analytics_tx_scroll,
                text=f"{sign}{format_inr(float(row['amount']))}",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=badge_color,
                width=120,
                anchor="e",
            )
            amt_lbl.grid(row=idx, column=5, padx=6, pady=2, sticky="e")

            edit_btn = ctk.CTkButton(
                self.analytics_tx_scroll,
                text="✎ Edit",
                width=54,
                height=24,
                corner_radius=6,
                fg_color="#334155",
                hover_color="#d97706",
                text_color="#f8fafc",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=lambda tid=tx_id: self.start_edit_transaction(tid),
            )
            edit_btn.grid(row=idx, column=6, padx=3, pady=2, sticky="e")

            del_btn = ctk.CTkButton(
                self.analytics_tx_scroll,
                text="✕",
                width=26,
                height=24,
                corner_radius=6,
                fg_color="transparent",
                hover_color="#e11d48",
                text_color=self._color("text_secondary"),
                command=lambda tid=tx_id: self.handle_delete_transaction(tid),
            )
            del_btn.grid(row=idx, column=7, padx=(2, 6), pady=2, sticky="e")

    def _set_status(self, message: str, is_error: bool = False) -> None:
        """Display validation or confirmation status text in the sidebar."""
        color = self._color("expense") if is_error else self._color("income")
        self.status_label.configure(text=message, text_color=color)

    def toggle_appearance_mode(self, new_mode: str) -> None:
        """Switch between Dark and Light mode and re-style UI cards and Matplotlib charts."""
        self.appearance_mode = new_mode
        ctk.set_appearance_mode(new_mode)

        self.configure(fg_color=self._color("window_bg"))
        self.sidebar_frame.configure(
            fg_color=self._color("sidebar_bg"),
            border_color=self._color("card_border"),
        )
        for card in (
            self.nav_card,
            self.form_card,
            self.income_card,
            self.expense_card,
            self.balance_card,
            self.line_chart_card,
            self.donut_chart_card,
            self.recent_card,
            self.filter_card,
            self.akpi_inc_card,
            self.akpi_exp_card,
            self.akpi_net_card,
            self.bar_chart_card,
            self.analytics_cat_card,
            self.analytics_table_card,
        ):
            card.configure(
                fg_color=self._color("card_bg"),
                border_color=self._color("card_border"),
            )

        for lbl in (
            self.title_label,
            self.form_header_lbl,
            self.dashboard_title,
            self.line_chart_title,
            self.donut_chart_title,
            self.recent_title,
            self.analytics_header_lbl,
            self.bar_chart_title,
            self.analytics_cat_title,
            self.analytics_table_title,
        ):
            lbl.configure(text_color=self._color("text_primary"))

        self.subtitle_label.configure(text_color=self._color("text_secondary"))
        for btn in (self.reset_mock_btn, self.clear_mock_btn):
            btn.configure(
                border_color=self._color("card_border"),
                text_color=self._color("text_primary"),
                hover_color=self._color("card_bg"),
            )

        self.switch_page(self.active_page)
        self.refresh_all_views()

    def on_close(self) -> None:
        """Cleanly close SQLite connection and terminate Tk mainloop."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        self.quit()
        self.destroy()


def run_self_test() -> None:
    """
    Headless verification helper that tests:
    1. INR mock data seeding with multiple Income Modes & Expense Categories
    2. Editing an existing fed transaction via `start_edit_transaction` + `handle_save_or_update_transaction`
    3. Rendering the Advanced Pie Chart in all 3 modes ('Income + Expense', 'Income Modes', 'Expenses')
    """
    app = App(db_path=DB_PATH)
    app.update_idletasks()

    # Verify Income Modes breakdown
    inc_modes = app.fetch_category_breakdown("Income")
    exp_cats = app.fetch_category_breakdown("Expense")

    # Test inserting, editing, and deleting a temporary transaction without altering user data
    app.insert_transaction("2026-11-05", "Income", "Freelance & Consulting", 5000.0, "Temp self-test")
    rows = app.fetch_filtered_transactions(limit=1)
    if rows:
        temp_id = int(rows[0]["id"])
        app.start_edit_transaction(temp_id)
        app.amount_entry.delete(0, "end")
        app.amount_entry.insert(0, "7500.00")
        app.handle_save_or_update_transaction()
        app.delete_transaction(temp_id)
        app.refresh_all_views()

    # Test switching advanced pie chart modes
    for mode in ("Income Modes", "Expenses", "Income + Expense"):
        app.dash_pie_mode_var.set(mode)
        app.draw_expense_donut_chart()

    summary = app.fetch_monthly_summary()
    print(
        f"[Self-Test Full Edit + Income Pie] Income: {format_inr(summary['income'])} "
        f"({len(inc_modes)} income modes) | "
        f"Expenses: {format_inr(summary['expense'])} ({len(exp_cats)} expense categories) | "
        f"Net: {format_inr(summary['net_balance'])}"
    )
    app.after(400, app.on_close)
    app.mainloop()
    print("[Self-Test] Full Edit CRUD & Advanced Income/Expense Pie Charts verified.")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        run_self_test()
    else:
        finance_app = App()
        finance_app.mainloop()
