"""Generate a sustainability compliance dashboard for CTRL Environmental.

The script reads inspection data from CSV or Excel files, categorizes findings
into environmental topics, flags non-compliances with traffic-light colours,
and exports the results to a styled HTML report. Optional PDF export is
attempted, preferring WeasyPrint with a fallback to pdfkit when available.
The layout uses a black, red, and white palette reminiscent of Berlin poster
art and includes placeholders for the CTRL logo and report metadata.
"""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Optional PDF backends
try:
    import pdfkit
except ImportError:  # pragma: no cover - optional dependency
    pdfkit = None  # type: ignore[assignment]
try:
    from weasyprint import HTML
except ImportError:  # pragma: no cover - optional dependency
    HTML = None  # type: ignore[assignment]

logging.basicConfig(level=logging.INFO)

# Regex for safer status parsing
_NEG = re.compile(
    r"\b(?:major\s*nc|fail|non[-\s]?compliance|(?:^|[^a-z])nc(?:$|[^a-z]))\b", re.I
)
_AMB = re.compile(r"\b(?:minor|observation|warning)\b", re.I)

CATEGORY_KEYWORDS = {
    "Waste": ["waste", "trash", "garbage", "recycle"],
    "Water": ["water", "effluent", "sewage", "storm"],
    "Air": ["air", "emission", "dust", "smoke"],
    "Chemicals": ["chemical", "hazard", "solvent", "acid", "alkali"],
    "ESG": ["esg", "governance", "social", "sustainability", "diversity"],
}


@dataclass
class Metadata:
    """Metadata describing the inspection report."""

    site: str
    client: str
    inspector: str
    logo: str
    date: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    )


def read_inspection_data(path: str) -> pd.DataFrame:
    """Read inspection data from a CSV or Excel file."""

    ext = Path(path).suffix.lower()
    if ext in {".xls", ".xlsx"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def categorize_finding(text: str) -> str:
    """Return the category that best matches *text*."""

    lowered = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(word in lowered for word in keywords):
            return category
    return "Other"


def traffic_light(status: str) -> str:
    """Return a CSS colour for a traffic-light style status."""

    s = (status or "").strip()
    if _NEG.search(s):
        return "#d50000"  # red
    if _AMB.search(s):
        return "#ffab00"  # amber
    return "#00c853"  # green


def style_dataframe(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Apply traffic-light styling to status columns in *df* and hide the index."""

    subset_cols = [c for c in df.columns if c.strip().lower() == "status"]
    styler = df.style
    if subset_cols:
        styler = styler.map(
            lambda v: f"background-color:{traffic_light(v)}", subset=subset_cols
        )
    return styler.hide(axis="index")


# Jinja environment
env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_report(
    df: pd.DataFrame, metadata: Metadata, html_out: str, pdf_out: str | None = None
) -> None:
    """Render *df* to HTML and optionally PDF."""

    styled_html = style_dataframe(df).to_html()
    template = env.get_template("report.html.j2")
    report_html = template.render(metadata=metadata, table_html=styled_html)

    Path(html_out).write_text(report_html, encoding="utf-8")
    logging.info("Report written to %s", html_out)

    if pdf_out:
        if HTML:
            try:
                HTML(filename=html_out).write_pdf(pdf_out)  # type: ignore[no-untyped-call]
                logging.info("PDF written via WeasyPrint to %s", pdf_out)
                return
            except Exception as exc:  # noqa: BLE001  # pragma: no cover - optional dependency
                logging.warning("WeasyPrint failed (%s); falling back to pdfkit", exc)
        if pdfkit:
            try:
                pdfkit.from_file(html_out, pdf_out)  # type: ignore[no-untyped-call]
                logging.info("PDF written via pdfkit to %s", pdf_out)
            except OSError as exc:  # wkhtmltopdf missing
                logging.warning("pdfkit failed (%s); skipped PDF export", exc)
        else:
            logging.warning("No PDF backend available; skipped PDF export")


def main() -> None:
    """Command line interface for the compliance dashboard."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="CSV or Excel file containing inspection data")
    parser.add_argument("--html", default="report.html", help="Output HTML report path")
    parser.add_argument("--pdf", help="Optional output PDF path")
    parser.add_argument(
        "--logo", default="logo_placeholder.png", help="Path to CTRL logo"
    )
    parser.add_argument("--site", default="Unknown Site")
    parser.add_argument("--client", default="Unknown Client")
    parser.add_argument("--inspector", default="Unknown Inspector")
    parser.add_argument("--date", help="Report date (defaults to now UTC)")
    args = parser.parse_args()

    data = read_inspection_data(args.input)
    if "Category" not in data.columns and "Finding" in data.columns:
        data["Category"] = data["Finding"].map(categorize_finding)

    meta_kwargs = {
        "site": args.site,
        "client": args.client,
        "inspector": args.inspector,
        "logo": args.logo,
    }
    if args.date:
        meta_kwargs["date"] = args.date
    metadata = Metadata(**meta_kwargs)
    render_report(data, metadata, args.html, args.pdf)
    print(f"Report written to {args.html}")


if __name__ == "__main__":
    main()
