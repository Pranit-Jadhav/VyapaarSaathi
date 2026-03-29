"""
Backend PDF report generator for VyapaarSaathi.

Generates a formal "Trading & Profit & Loss A/c" statement in the standard
Indian IT-return filing format. Pulls real data from Supabase ledger and
inventory tables. Uploads the PDF to Supabase storage and returns a
publicly-accessible URL suitable for WhatsApp delivery.
"""

import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fpdf import FPDF

from supabase_config import get_supabase

logger = logging.getLogger(__name__)

TABLE = "inventory"
LEDGER = "ledger"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_inr(n: float) -> str:
    """Format number in Indian number system: 34,10,000.00"""
    sign = "-" if n < 0 else ""
    n = abs(n)
    int_part = int(n)
    dec_part = f"{n - int_part:.2f}"[2:]
    s = str(int_part)
    if len(s) <= 3:
        formatted = s
    else:
        formatted = s[-3:]
        remaining = s[:-3]
        while len(remaining) > 2:
            formatted = remaining[-2:] + "," + formatted
            remaining = remaining[:-2]
        formatted = remaining + "," + formatted
    return f"{sign}{formatted}.{dec_part}"


def _fmt_date_formal(d: date) -> str:
    """e.g. '31st March 2026'"""
    day = d.day
    if 11 <= day <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    return f"{day}{suffix} {months[d.month - 1]} {d.year}"


def _today_str() -> str:
    return date.today().isoformat()


# ─── Fetch ledger + inventory data ────────────────────────────────────────────

def _fetch_all_data(phone: str) -> Dict[str, Any]:
    """
    Fetch all ledger entries and inventory data for the vendor.
    Returns a dict with structured financial data for the P&L statement.
    Uses last 30 days to match the AI Insights date window exactly.
    """
    supabase = get_supabase()
    today = datetime.now(timezone.utc)
    # Use same 30-day window as AI Insights so numbers always match
    start_30d = today - timedelta(days=30)
    start_iso = start_30d.replace(hour=0, minute=0, second=0).isoformat()
    start_date = start_30d.date()

    # ── Ledger entries ────────────────────────────────────────────────────────
    entries = []

    if phone == "web-client":
        result = (
            supabase.table(LEDGER)
            .select("*")
            .gte("created_at", start_iso)
            .order("created_at", desc=False)
            .execute()
        )
        if result.data:
            entries = result.data
    else:
        phones_to_fetch = [phone, "web-client"]
        result = (
            supabase.table(LEDGER)
            .select("*")
            .in_("phone", phones_to_fetch)
            .gte("created_at", start_iso)
            .order("created_at", desc=False)
            .execute()
        )
        if result.data:
            entries = result.data

    # ── Inventory (for opening/closing stock valuation) ────────────────────
    inv_rows = []
    for try_phone in [phone, "web-client"] if phone != "web-client" else [phone]:
        inv_result = (
            supabase.table(TABLE)
            .select("*")
            .eq("phone", try_phone)
            .eq("stock_date", date.today().isoformat())
            .eq("is_active", True)
            .execute()
        )
        if inv_result.data:
            inv_rows = inv_result.data
            break

    # ── Aggregate ─────────────────────────────────────────────────────────────
    # Income (Sales) by category
    income_by_cat: Dict[str, float] = defaultdict(float)
    # Expenses by category
    expense_by_cat: Dict[str, float] = defaultdict(float)
    total_income = 0.0
    total_expense = 0.0

    for e in entries:
        raw_cat = str(e.get("category") or "General").strip().lower()
        normalized_cat = raw_cat.replace(" ", "")
        
        # Normalize exact demo items to merge correctly
        if "vadapa" in normalized_cat or "vadapan" in normalized_cat:
            cat = "Vada Pav"
        elif "samosa" in normalized_cat:
            cat = "Samosa"
        elif "chai" in normalized_cat:
            cat = "Chai"
        elif "kachori" in normalized_cat:
            cat = "Kachori"
        elif "pavbhaji" in normalized_cat:
            cat = "Pav Bhaji"
        elif "coffee" in normalized_cat:
            cat = "Coffee"
        else:
            cat = raw_cat.title()

        try:
            amt = float(e.get("amount") or 0)
        except (TypeError, ValueError):
            amt = 0.0
        if e.get("type") == "income":
            income_by_cat[cat] += amt
            total_income += amt
        elif e.get("type") == "expense":
            expense_by_cat[cat] += amt
            total_expense += amt

    # Stock valuation
    opening_stock = 0.0
    closing_stock = 0.0
    for inv in inv_rows:
        try:
            price = float(inv.get("price_per_unit") or 0)
            daily = int(inv.get("daily_stock") or 0)
            current = int(inv.get("current_stock") or 0)
        except (TypeError, ValueError):
            price = daily = current = 0
        opening_stock += daily * price
        closing_stock += current * price

    return {
        "entries": entries,
        "income_by_cat": dict(income_by_cat),
        "expense_by_cat": dict(expense_by_cat),
        "total_income": total_income,
        "total_expense": total_expense,
        "opening_stock": opening_stock,
        "closing_stock": closing_stock,
        "inventory": inv_rows,
        "start_date": start_date,
        "end_date": date.today(),
    }


# ─── PDF Generation — IT Return P&L Format ───────────────────────────────────

class PnLPDF(FPDF):
    """Custom FPDF subclass for the T-account P&L layout."""

    def __init__(self):
        super().__init__(orientation="P", unit="pt", format="A4")
        self.ml = 40        # margin left
        self.mr = 40        # margin right
        self.pw = 595.28    # A4 width in pt
        self.cw = self.pw - self.ml - self.mr  # content width ~515

        # Column layout: left half (debit) | right half (credit)
        self.half_w = self.cw / 2
        self.left_label_x = self.ml
        self.left_amt_x = self.ml + self.half_w - 10   # right-edge of left amounts
        self.right_label_x = self.ml + self.half_w + 5
        self.right_amt_x = self.pw - self.mr - 5        # right-edge of right amounts
        self.divider_x = self.ml + self.half_w          # center vertical line

    def _draw_header(self, vendor_name: str, start_date: date, end_date: date):
        """Draw the company header block."""
        y = 36

        # Company name — bold, centered, large
        self.set_font("Helvetica", "B", 16)
        self.set_xy(self.ml, y)
        self.cell(self.cw, 18, vendor_name.upper(), align="C")
        y += 22

        # (PROP : NAME)
        self.set_font("Helvetica", "", 10)
        self.set_xy(self.ml, y)
        self.cell(self.cw, 14, f"(PROP : {vendor_name.upper()})", align="C")
        y += 18

        # Title: "Trading & Profit & Loss A/c for the period ended ..."
        self.set_font("Helvetica", "B", 11)
        self.set_xy(self.ml, y)
        period_text = f"Trading & Profit & Loss A/c for the period ended {_fmt_date_formal(end_date)}"
        self.cell(self.cw, 16, period_text, align="C")
        y += 26

        return y

    def _draw_column_headers(self, y: float) -> float:
        """Draw 'Particulars  Amount  Particulars  Amount' header row."""
        self.set_line_width(0.8)
        self.line(self.ml, y, self.pw - self.mr, y)
        y += 4

        self.set_font("Helvetica", "B", 10)
        # Left: Particulars + Amount
        self.set_xy(self.left_label_x + 2, y)
        self.cell(self.half_w * 0.65, 14, "Particulars")
        self.set_xy(self.left_amt_x - 60, y)
        self.cell(70, 14, "Amount", align="R")

        # Right: Particulars + Amount
        self.set_xy(self.right_label_x + 2, y)
        self.cell(self.half_w * 0.65, 14, "Particulars")
        self.set_xy(self.right_amt_x - 60, y)
        self.cell(70, 14, "Amount", align="R")

        y += 16
        self.set_line_width(0.5)
        self.line(self.ml, y, self.pw - self.mr, y)
        y += 4

        return y

    def _draw_row(self, y: float, left_label: str = "", left_amt: str = "",
                  right_label: str = "", right_amt: str = "",
                  bold: bool = False, left_bold_amt: bool = False,
                  right_bold_amt: bool = False) -> float:
        """Draw one row across both columns."""
        font_style = "B" if bold else ""
        self.set_font("Helvetica", font_style, 10)

        if left_label:
            self.set_xy(self.left_label_x + 5, y)
            self.cell(self.half_w * 0.6, 14, left_label)
        if left_amt:
            self.set_font("Helvetica", "B" if (bold or left_bold_amt) else "", 10)
            self.set_xy(self.left_amt_x - 70, y)
            self.cell(80, 14, left_amt, align="R")

        self.set_font("Helvetica", font_style, 10)
        if right_label:
            self.set_xy(self.right_label_x + 5, y)
            self.cell(self.half_w * 0.6, 14, right_label)
        if right_amt:
            self.set_font("Helvetica", "B" if (bold or right_bold_amt) else "", 10)
            self.set_xy(self.right_amt_x - 70, y)
            self.cell(80, 14, right_amt, align="R")

        return y + 16

    def _draw_total_rule(self, y: float) -> float:
        """Draw double rule for totals (like the reference image)."""
        self.set_line_width(1.0)
        self.line(self.ml, y, self.pw - self.mr, y)
        self.set_line_width(0.4)
        self.line(self.ml, y + 3, self.pw - self.mr, y + 3)
        return y + 8

    def _draw_separator_rule(self, y: float) -> float:
        """Single thin rule to separate sections."""
        self.set_line_width(0.5)
        self.line(self.ml, y, self.pw - self.mr, y)
        return y + 4

    def _draw_divider(self, y_start: float, y_end: float):
        """Draw the vertical center divider line."""
        self.set_line_width(0.5)
        self.line(self.divider_x, y_start, self.divider_x, y_end)


def generate_pnl_pdf(phone: str, vendor_name: str = "Vendor") -> Optional[str]:
    """
    Generate a formal Trading & Profit & Loss A/c PDF.
    Matches the standard Indian IT-return filing format.

    Uploads to Supabase storage and returns the public URL.
    Returns None if no data is found.
    """
    data = _fetch_all_data(phone)
    if not data["entries"]:
        return None

    total_sales = data["total_income"]
    total_purchases = data["total_expense"]
    opening_stock = data["opening_stock"]
    closing_stock = data["closing_stock"]
    income_by_cat = data["income_by_cat"]
    expense_by_cat = data["expense_by_cat"]
    start_date = data["start_date"]
    end_date = data["end_date"]

    # ── Core Numbers ─────────────────────────────────────────────────────────
    # Trading Account gross profit (stock-adjusted):
    #   Credit side: Sales + Closing Stock
    #   Debit side:  Opening Stock + Purchases + Gross Profit  → must balance
    credit_total_trading = total_sales + closing_stock
    debit_before_gp = opening_stock + total_purchases
    gross_profit = credit_total_trading - debit_before_gp   # = Sales + Closing - Opening - Purchases

    if gross_profit < 0:
        gross_loss = abs(gross_profit)
        gross_profit = 0.0
    else:
        gross_loss = 0.0

    # Trading account total (both sides must equal this):
    trading_balance = credit_total_trading  # Sales + Closing Stock

    # ── P&L Account ──────────────────────────────────────────────────────────
    # The P&L account receives "By Gross Profit b/d" from Trading Account.
    # Since all expenses are captured as "Purchases" in Trading Account,
    # there are NO indirect expenses in P&L.
    # Therefore: Net Profit = Gross Profit  (P&L balances exactly)
    net_profit_pnl = gross_profit   # what appears in both P&L columns
    pnl_balance = gross_profit      # both sides of P&L = gross_profit

    # Clean vendor name
    display_name = vendor_name or "VENDOR"
    if display_name.startswith("whatsapp:"):
        display_name = display_name.replace("whatsapp:", "").strip()
        
    # If the remaining string is just a phone number (mostly digits/plus) or a generic key
    clean_for_check = display_name.replace("+", "").strip()
    if clean_for_check.isdigit() or display_name == "web-client":
        display_name = "VENDOR"

    # ── Build PDF ─────────────────────────────────────────────────────────────
    pdf = PnLPDF()
    pdf.add_page()

    # Header
    y = pdf._draw_header(display_name, start_date, end_date)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 1: TRADING ACCOUNT
    # ═══════════════════════════════════════════════════════════════════════════
    section1_start_y = y
    y = pdf._draw_column_headers(y)
    body_start_y = y

    # LEFT (Debit): To Opening Stock, To Purchases, To Gross Profit
    left_y = y
    left_y = pdf._draw_row(left_y,
                           left_label="To Opening Stock",
                           left_amt=_fmt_inr(opening_stock))

    # Individual purchase/expense items under "To Purchases"
    if expense_by_cat:
        left_y = pdf._draw_row(left_y,
                               left_label="To Purchases",
                               left_amt=_fmt_inr(total_purchases))
    else:
        left_y = pdf._draw_row(left_y,
                               left_label="To Purchases",
                               left_amt=_fmt_inr(total_purchases))

    left_y = pdf._draw_row(left_y,
                           left_label="To Gross Profit",
                           left_amt=_fmt_inr(gross_profit))

    # RIGHT (Credit): By Sales (with breakdown), By Closing Stock
    right_y = y

    # Individual sales categories
    for cat_name, cat_amt in sorted(income_by_cat.items()):
        right_y = pdf._draw_row(right_y,
                                right_label=f"By Sales ({cat_name})",
                                right_amt=_fmt_inr(cat_amt))

    right_y = pdf._draw_row(right_y,
                            right_label="By Closing Stock",
                            right_amt=_fmt_inr(closing_stock))

    # Align both sides to the same level
    max_y = max(left_y, right_y) + 2

    # Separator
    max_y = pdf._draw_separator_rule(max_y)

    # TOTAL ROW (Trading Account)
    max_y = pdf._draw_row(max_y,
                          left_amt=_fmt_inr(trading_balance),
                          right_amt=_fmt_inr(trading_balance),
                          bold=True)

    # Double rule
    max_y = pdf._draw_total_rule(max_y)

    # Draw vertical divider for Trading section
    pdf._draw_divider(body_start_y - 4, max_y - 4)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 2: PROFIT & LOSS ACCOUNT
    # ═══════════════════════════════════════════════════════════════════════════
    section2_start_y = max_y + 6
    y = section2_start_y

    # Column headers again
    y = pdf._draw_column_headers(y)
    pnl_body_start_y = y

    # LEFT (Debit): Net Profit (or nothing if net loss)
    left_y = y

    if net_profit_pnl >= 0:
        # Net Profit on debit side (standard format)
        left_y = pdf._draw_row(left_y,
                               left_label="To Net Profit c/d",
                               left_amt=_fmt_inr(net_profit_pnl),
                               left_bold_amt=True)
    else:
        left_y = pdf._draw_row(left_y,
                               left_label="(Net Loss)",
                               left_amt=_fmt_inr(0))

    # RIGHT (Credit): By Gross Profit b/d
    right_y = y
    right_y = pdf._draw_row(right_y,
                            right_label="By Gross Profit b/d",
                            right_amt=_fmt_inr(gross_profit),
                            right_bold_amt=True)

    if net_profit_pnl < 0:
        right_y = pdf._draw_row(right_y,
                                right_label="By Net Loss",
                                right_amt=_fmt_inr(abs(net_profit_pnl)),
                                right_bold_amt=True)

    # Align both sides
    max_y = max(left_y, right_y) + 2

    # Separator
    max_y = pdf._draw_separator_rule(max_y)

    # TOTAL ROW (P&L Account) — both sides = gross_profit
    max_y = pdf._draw_row(max_y,
                          left_amt=_fmt_inr(pnl_balance),
                          right_amt=_fmt_inr(pnl_balance),
                          bold=True)

    # Double rule
    max_y = pdf._draw_total_rule(max_y)

    # Draw vertical divider for P&L section
    pdf._draw_divider(pnl_body_start_y - 4, max_y - 4)

    # ═══════════════════════════════════════════════════════════════════════════
    # FOOTER: Proprietor signature block
    # ═══════════════════════════════════════════════════════════════════════════
    y = max_y + 30

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(pdf.ml, y)
    pdf.cell(pdf.cw, 14, f"For {display_name.upper()}", align="R")
    y += 50

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(pdf.ml, y)
    pdf.cell(pdf.cw, 14, "(Proprietor)", align="R")
    y += 16

    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(pdf.ml, y)
    pdf.cell(pdf.cw, 12, f"Place: India", align="R")
    y += 12
    pdf.set_xy(pdf.ml, y)
    pdf.cell(pdf.cw, 12,
             f"Date: {end_date.strftime('%d/%m/%Y')}",
             align="R")

    # Small footer
    y += 30
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_xy(pdf.ml, y)
    pdf.cell(pdf.cw, 10,
             f"Generated by VyapaarSaathi | Period: {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}",
             align="C")

    # ── Upload ────────────────────────────────────────────────────────────────
    safe_phone = phone.replace("+", "").replace(":", "_").replace(" ", "_")
    file_name = f"pnl_{safe_phone}_{uuid.uuid4().hex[:8]}.pdf"
    pdf_bytes = bytes(pdf.output())

    try:
        supabase = get_supabase()
        supabase.storage.from_("reports").upload(
            file_name,
            pdf_bytes,
            file_options={"content-type": "application/pdf"},
        )
        public_url = supabase.storage.from_("reports").get_public_url(file_name)
        logger.info("P&L report uploaded: %s", public_url)
        return public_url
    except Exception as upload_exc:
        logger.error("Failed to upload P&L report: %s", upload_exc)
        return None
