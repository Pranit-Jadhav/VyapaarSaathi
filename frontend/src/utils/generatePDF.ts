import { jsPDF } from "jspdf";
import { Entry, toNumber, isSameWeek } from "../store/useStore";

// ─── helpers ────────────────────────────────────────────────────────────────

function fmtDate(d: Date): string {
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${d.getDate()}-${months[d.getMonth()]}-${d.getFullYear()}`;
}

function fmtAmt(n: number): string {
    // Indian number format: 1,00,000.00
    const [intPart, decPart] = Math.abs(n).toFixed(2).split(".");
    let result = "";
    const int = intPart;
    if (int.length <= 3) {
        result = int;
    } else {
        result = int.slice(-3);
        let remaining = int.slice(0, -3);
        while (remaining.length > 2) {
            result = remaining.slice(-2) + "," + result;
            remaining = remaining.slice(0, -2);
        }
        result = remaining + "," + result;
    }
    return (n < 0 ? "-" : "") + result + "." + decPart;
}

// ─── main export ─────────────────────────────────────────────────────────────

/**
 * Generates a Profit & Loss PDF that exactly matches the J.S. Bhatia & Co.
 * reference format (RBI / CA-certified style).
 *
 * Layout (portrait A4):
 *   • Top-left:   "Profit & Loss A/c" + date range
 *   • Center col: Company name + date range  (acts as the divider header)
 *   • Two-column body separated by a vertical rule
 *   • Left  column: Expenses (indented under section labels) + Nett Profit
 *   • Right column: Incomes (indented under section labels)
 *   • Total row: bold, double-ruled
 *   • Footer: CA firm left, proprietor right, signature gap
 */
export function generatePnLPDF(entries: Entry[], userName: string): void {
    const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "a4" });
    const PW = doc.internal.pageSize.getWidth();   // 595.28
    const PH = doc.internal.pageSize.getHeight();  // 841.89

    const ML = 40;   // margin left
    const MR = 40;   // margin right
    const CW = PW - ML - MR;  // content width  515.28

    // Column geometry — mirrors reference exactly
    const expLabelX = ML;                        // expense particulars start
    const expAmtX = ML + 220;                  // expense amount right-edge
    const dividerX = ML + 257;                  // center vertical rule
    const incLabelX = dividerX + 10;             // income particulars start
    const incAmtX = PW - MR;                   // income amount right-edge (mostly blank in ref)

    // ── 1. Aggregate data ────────────────────────────────────────────────────

    // We store items as { label, amount } preserving insertion order
    const expItems: { label: string; amount: number }[] = [];
    const incItems: { label: string; amount: number }[] = [];
    const expMap: Record<string, number> = {};
    const incMap: Record<string, number> = {};

    for (const entry of entries) {
        if (Array.isArray(entry.expenses)) {
            for (const exp of entry.expenses as any[]) {
                if (!exp) continue;
                const label = (exp.item_name || exp.category || "MISC EXPENSE").toUpperCase().trim();
                const amt = toNumber(exp.amount) || 0;
                expMap[label] = (expMap[label] || 0) + amt;
            }
        }
        if (Array.isArray(entry.items_sold)) {
            for (const item of entry.items_sold as any[]) {
                if (!item) continue;
                const label = (item.item_name || item.name || "SALES").toUpperCase().trim();
                const amt = toNumber(item.amount) || toNumber(item.total_price) || 0;
                incMap[label] = (incMap[label] || 0) + amt;
            }
        }
    }

    for (const [label, amount] of Object.entries(expMap)) expItems.push({ label, amount });
    for (const [label, amount] of Object.entries(incMap)) incItems.push({ label, amount });

    const totalExpense = expItems.reduce((s, x) => s + x.amount, 0);
    const totalIncome = incItems.reduce((s, x) => s + x.amount, 0);
    const netProfit = totalIncome - totalExpense;
    const balTotal = Math.max(totalIncome, totalExpense);

    // ── 2. Date range ─────────────────────────────────────────────────────────

    const dates = entries
        .map(e => new Date(e.entry_date!))
        .filter(d => !isNaN(d.getTime()));
    let dateRange = "";
    if (dates.length > 0) {
        const minD = new Date(Math.min(...dates.map(d => d.getTime())));
        const maxD = new Date(Math.max(...dates.map(d => d.getTime())));
        dateRange = `${fmtDate(minD)} to ${fmtDate(maxD)}`;
    } else {
        const now = new Date();
        dateRange = `1-Apr-${now.getFullYear() - 1} to 31-Mar-${now.getFullYear()}`;
    }

    const companyName = (userName || "PROPRIETOR").toUpperCase();

    // ── 3. Top header ─────────────────────────────────────────────────────────

    let y = 36;

    // Top-left: "Profit & Loss A/c" bold italic
    doc.setFont("helvetica", "bolditalic");
    doc.setFontSize(11);
    doc.text("Profit & Loss A/c", ML, y);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(8.5);
    doc.text(dateRange, ML, y + 13);

    // Center column header: company name + date range
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.text(companyName, dividerX + (incAmtX - dividerX) / 2 + (expAmtX - ML) / 2, y, { align: "center" });

    doc.setFont("helvetica", "normal");
    doc.setFontSize(8.5);
    doc.text(dateRange, dividerX + (incAmtX - dividerX) / 2 + (expAmtX - ML) / 2, y + 13, { align: "center" });

    // Full-width horizontal rule under header
    y += 26;
    doc.setLineWidth(1);
    doc.line(ML, y, PW - MR, y);

    // ── 4. Column headers row ─────────────────────────────────────────────────

    y += 14;
    doc.setFont("helvetica", "bold");
    doc.setFontSize(9);
    doc.text("Particulars", expLabelX, y);
    doc.text("Particulars", incLabelX, y);

    // Thin rule under column headers
    y += 4;
    doc.setLineWidth(0.5);
    doc.line(ML, y, PW - MR, y);

    // ── 5. Body rows ──────────────────────────────────────────────────────────

    const ROW_H = 14;   // row height pt
    const INDENT = 10;   // indent for items under section label

    y += ROW_H - 2;

    // Section labels
    // LEFT: "Purchase Accounts" → "Indirect Expenses" (bold) with sub-total
    // RIGHT: "Direct Incomes" → items  then "Indirect Incomes" → items

    // We'll draw left and right in parallel, tracking separate y positions
    // then reconcile at the end.

    // Collect left rows: section labels + items + net profit placeholder
    type Row = { text: string; amount?: number; bold?: boolean; italic?: boolean; indent?: boolean; isSection?: boolean };

    const leftRows: Row[] = [
        { text: "Purchase Accounts", bold: false, isSection: true },
        { text: "Indirect Expenses", bold: true, amount: totalExpense, isSection: true },
    ];
    for (const e of expItems) {
        leftRows.push({ text: e.label, amount: e.amount, indent: true });
    }

    // Right rows
    const rightRows: Row[] = [
        { text: "Direct Incomes", bold: false, isSection: true },
    ];
    // Separate income into "direct" (we treat all as direct for simplicity)
    for (const inc of incItems) {
        rightRows.push({ text: inc.label, amount: inc.amount, indent: true });
    }
    // If there were indirect incomes you'd add another section header here

    const startBodyY = y;
    let leftY = startBodyY;
    let rightY = startBodyY;

    // ── Draw left column ──────────────────────────────────────────────────────

    doc.setLineWidth(0.5);

    for (const row of leftRows) {
        const x = row.indent ? expLabelX + INDENT : expLabelX;

        if (row.bold || row.isSection) {
            doc.setFont("helvetica", row.bold ? "bold" : "normal");
        } else {
            doc.setFont("helvetica", "normal");
        }
        doc.setFontSize(8.5);
        doc.text(row.text, x, leftY);

        // Section subtotal (e.g. Indirect Expenses total) aligned to expAmtX
        if (row.isSection && row.amount !== undefined && row.amount > 0) {
            doc.setFont("helvetica", "bold");
            doc.text(fmtAmt(row.amount), expAmtX, leftY, { align: "right" });
        } else if (!row.isSection && row.amount !== undefined) {
            doc.setFont("helvetica", "normal");
            doc.text(fmtAmt(row.amount), expAmtX, leftY, { align: "right" });
        }

        leftY += ROW_H;
    }

    // ── Draw right column ─────────────────────────────────────────────────────

    for (const row of rightRows) {
        const x = row.indent ? incLabelX + INDENT : incLabelX;

        if (row.bold || row.isSection) {
            doc.setFont("helvetica", row.bold ? "bold" : "normal");
        } else {
            doc.setFont("helvetica", "normal");
        }
        doc.setFontSize(8.5);
        doc.text(row.text, x, rightY);

        // Income amounts on the right (right-aligned to incAmtX)
        if (!row.isSection && row.amount !== undefined && row.amount > 0) {
            doc.text(fmtAmt(row.amount), incAmtX, rightY, { align: "right" });
        }

        rightY += ROW_H;
    }

    // ── 6. Nett Profit / Loss row ─────────────────────────────────────────────

    // Position after whichever column is longer, with a gap
    const bodyBottom = Math.max(leftY, rightY) + 4;

    // Thin rule above Nett Profit (left side only — matches reference)
    doc.setLineWidth(0.5);
    doc.line(ML, bodyBottom - 2, dividerX - 2, bodyBottom - 2);

    doc.setFont("helvetica", "bold");
    doc.setFontSize(8.5);

    if (netProfit >= 0) {
        doc.text("Nett Profit", expLabelX, bodyBottom + ROW_H - 4);
        doc.text(fmtAmt(netProfit), expAmtX, bodyBottom + ROW_H - 4, { align: "right" });
    } else {
        // Net loss goes on the RIGHT (income) side
        doc.text("Nett Loss", incLabelX, bodyBottom + ROW_H - 4);
        doc.text(fmtAmt(Math.abs(netProfit)), incAmtX, bodyBottom + ROW_H - 4, { align: "right" });
    }

    // ── 7. Total row ──────────────────────────────────────────────────────────

    const totalY = bodyBottom + ROW_H * 2;

    // Double rule above Total (left + right)
    doc.setLineWidth(1.2);
    doc.line(ML, totalY - 6, PW - MR, totalY - 6);
    doc.setLineWidth(0.4);
    doc.line(ML, totalY - 3, PW - MR, totalY - 3);

    doc.setFont("helvetica", "bold");
    doc.setFontSize(9);
    doc.text("Total", expLabelX, totalY + 4);
    doc.text(fmtAmt(balTotal), expAmtX, totalY + 4, { align: "right" });
    doc.text("Total", incLabelX, totalY + 4);
    doc.text(fmtAmt(balTotal), incAmtX, totalY + 4, { align: "right" });

    // Double rule below Total
    const totalBottomY = totalY + 10;
    doc.setLineWidth(1.2);
    doc.line(ML, totalBottomY, PW - MR, totalBottomY);
    doc.setLineWidth(0.4);
    doc.line(ML, totalBottomY + 3, PW - MR, totalBottomY + 3);

    // ── 8. Vertical center divider (full body height) ─────────────────────────

    doc.setLineWidth(0.8);
    doc.line(dividerX, startBodyY - ROW_H, dividerX, totalBottomY + 3);

    // ── 9. Footer / Signatures ────────────────────────────────────────────────

    const footerY = totalBottomY + 30;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8.5);

    // Left side: CA firm
    doc.text("For Kaveria & Associates", ML, footerY);
    doc.text("(Chartered Accountants)", ML, footerY + 12);
    doc.text("FRN: 123916W", ML, footerY + 24);

    // Right side: company
    doc.text(`For ${companyName}`, PW - MR, footerY, { align: "right" });

    // Signature gap (~50pt)
    const sigY = footerY + 75;

    // Left signatory
    doc.text("Manish Kumar Kaveria", ML, sigY);
    doc.text("(Proprietor)", ML, sigY + 12);
    doc.text("M.No.: 114822", ML, sigY + 24);
    doc.text("UDIN:", ML, sigY + 36);
    doc.text("Place: Mumbai", ML, sigY + 56);
    doc.text(`Date: ${fmtDate(new Date())}`, ML, sigY + 68);

    // Right signatory
    doc.text(userName || "Proprietor", PW - MR, sigY, { align: "right" });
    doc.text("(Proprietor)", PW - MR, sigY + 12, { align: "right" });
    doc.text("Place: Mumbai", PW - MR, sigY + 56, { align: "right" });
    doc.text(`Date: ${fmtDate(new Date())}`, PW - MR, sigY + 68, { align: "right" });

    // ── 10. Save ──────────────────────────────────────────────────────────────

    doc.save("Profit_and_Loss_Statement.pdf");
}

// ─── weekly wrapper ──────────────────────────────────────────────────────────

export function generateWeeklyReportPDF(allEntries: Entry[], userName: string): void {
    const today = new Date();
    const weekEntries = allEntries.filter(e => {
        if (!e.entry_date) return false;
        return isSameWeek(new Date(e.entry_date), today);
    });
    if (weekEntries.length === 0) {
        alert("No entries for the current week.");
        return;
    }
    generatePnLPDF(weekEntries, userName);
}