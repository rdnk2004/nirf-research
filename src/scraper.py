"""
NIRF University-category scraper.

Pulls two layers of data for each year/institution:
  1. Listing-page composite scores  (TLR, RPC, GO, OI, PR, overall score, rank)
  2. Individual "Data Submitted by Institution" PDF (raw faculty count,
     PhD student counts, placement numbers, financial/research figures)

Design goals (per the "make it better" ask):
  - Resumable: every fetched page/PDF is cached to disk; re-running the
    script skips anything already downloaded.
  - Rate-limited: polite delay between requests (NIRF is a government
    server on shared infra — don't hammer it).
  - Fails per-institution, not globally: a malformed PDF or a changed
    layout logs a warning and moves on instead of crashing the run.
  - Handles the URL-pattern change: pre-2020 uses nirfindia.org/<year>/...,
    2020+ uses nirfindia.org/Rankings/<year>/...
  - Writes incrementally: the CSV is appended to as results come in, so
    killing the script early doesn't lose completed work.

USAGE
    pip install -r requirements.txt
    python nirf_scraper.py --years 2017 2018 2019 2020 2021 2022 2023 2024 2025 --category University

Output
    output/nirf_university_raw.csv      -- one row per institution per year
    output/parse_failures.log           -- anything that didn't parse cleanly
    cache/html/...                      -- cached listing pages
    cache/pdf/...                       -- cached institution PDFs

KNOWN LIMITATION -- read before trusting the faculty-PhD numbers:
    The individual PDF's "Faculty Details" section only reliably yielded
    "Number of faculty members entered: <N>" in the samples this script
    was built against. Whether a per-faculty PhD/qualification breakdown
    follows that line could not be confirmed here (the sample PDFs may
    have been truncated in the tool that inspected them, not necessarily
    in the source PDF). The parser stores the FULL raw text of the
    "Faculty Details" section in the `faculty_section_raw` column
    regardless of whether the regexes below find anything in it --
    open that column for a few rows after your first run and check
    whether PhD-qualification data is sitting there unparsed. If it is,
    tell me what the surrounding text looks like and I'll extend the
    regex.
"""

import argparse
import csv
import json
import logging
import re
import time
from pathlib import Path

import pdfplumber
import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

BASE_DELAY_SECONDS = 1.5          # politeness delay between requests
MAX_RETRIES = 3
TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

CACHE_DIR = Path("cache")
HTML_CACHE = CACHE_DIR / "html"
PDF_CACHE = CACHE_DIR / "pdf"
OUTPUT_DIR = Path("output")
CSV_PATH = OUTPUT_DIR / "nirf_university_raw.csv"
FAIL_LOG_PATH = OUTPUT_DIR / "parse_failures.log"

# Used to correctly split "New Delhi Delhi" into city="New Delhi",
# state="Delhi" -- NIRF's listing text has no separator between city and
# state, so a naive "last word is the state" split breaks on any
# multi-word city name. Matching against real state names fixes it.
INDIAN_STATES_UTS = sorted([
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands",
    "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
    "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
], key=len, reverse=True)

# Rank-band suffixes NIRF uses to paginate a category's listing.
# The scraper stops once a page 404s or returns zero new institutions,
# so listing more than you need here is harmless.
PAGE_SUFFIXES = ["", "150", "200", "300", "400", "500"]

# Fields that come ONLY from the listing page. parse_institution_pdf must
# never initialize or touch these -- a prior version of this script
# initialized ALL fields (including these) to None inside
# parse_institution_pdf, and row.update(parsed) then silently overwrote
# the real listing data with those Nones. That bug is why an earlier run
# produced a CSV with blank year/institute_id/scores for every row.
LISTING_FIELDS = [
    "year", "institute_id", "name", "city", "state",
    "tlr_score", "rpc_score", "go_score", "oi_score", "pr_score",
    "overall_score", "rank", "pdf_url",
]

# Fields that come ONLY from the individual institution PDF.
PDF_FIELDS = [
    "faculty_count",
    "total_student_strength", "student_strength_breakdown",
    "phd_fulltime_current", "phd_parttime_current",
    "phd_graduated_fulltime_y1", "phd_graduated_parttime_y1",
    "phd_graduated_fulltime_y2", "phd_graduated_parttime_y2",
    "phd_graduated_fulltime_y3", "phd_graduated_parttime_y3",
    "sponsored_projects_y1", "sponsored_projects_y2", "sponsored_projects_y3",
    "sponsored_funding_agencies_y1", "sponsored_funding_agencies_y2", "sponsored_funding_agencies_y3",
    "sponsored_amount_y1", "sponsored_amount_y2", "sponsored_amount_y3",
    "parse_status", "faculty_section_raw",
]

CSV_FIELDS = LISTING_FIELDS + PDF_FIELDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("nirf_scraper")


# --------------------------------------------------------------------------
# Fetching (cached, retried, rate-limited)
# --------------------------------------------------------------------------

def _fetch_raw(url: str) -> bytes | None:
    """One HTTP GET with retries. Returns raw bytes, or None if it never succeeds."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            if resp.status_code == 200:
                return resp.content
            if resp.status_code == 404:
                return None  # don't retry a genuine 404
            log.warning("Got HTTP %s for %s (attempt %d/%d)", resp.status_code, url, attempt, MAX_RETRIES)
        except requests.RequestException as e:
            log.warning("Request error for %s: %s (attempt %d/%d)", url, e, attempt, MAX_RETRIES)
        time.sleep(BASE_DELAY_SECONDS * attempt)  # back off a bit more each retry
    log.error("Giving up on %s after %d attempts", url, MAX_RETRIES)
    return None


def fetch_cached(url: str, cache_path: Path) -> bytes | None:
    """Fetch a URL, using a local cache file if it already exists."""
    if cache_path.exists():
        return cache_path.read_bytes()
    time.sleep(BASE_DELAY_SECONDS)
    content = _fetch_raw(url)
    if content is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(content)
    return content


def listing_url_candidates(year: int, category: str, page_suffix: str) -> list[str]:
    """
    NIRF changed its URL scheme around 2020. Try the modern pattern first,
    fall back to the legacy one. Both are tried because some years work
    under one, some under the other, and a couple of years respond to both.
    """
    page = f"{category}Ranking{page_suffix}.html"
    return [
        f"https://www.nirfindia.org/Rankings/{year}/{page}",
        f"https://www.nirfindia.org/{year}/{page}",
    ]


# --------------------------------------------------------------------------
# Listing page parsing
# --------------------------------------------------------------------------

def parse_listing_html(html: bytes, year: int, category: str) -> list[dict]:
    """
    Extract one row per institution from a rendered listing page.
    NIRF's listing tables use a nested "grid inside a table cell" layout
    (see the raw markdown dump we inspected before writing this) rather
    than a clean <table><tr><td> per field, so we parse it defensively:
    walk every table row, and inside it look for the labelled TLR/RPC/GO/
    OI/PERCEPTION mini-table plus the institute code and PDF link.
    """
    soup = BeautifulSoup(html, "lxml")
    rows = []

    # Every institution block contains an "IR-..." institute code and a
    # link to its individual PDF ending in "<code>.pdf" -- anchor on that
    # PDF link since it's the most structurally reliable marker per row.
    for pdf_link in soup.find_all("a", href=re.compile(r"/nirfpdfcdn/.*\.pdf$", re.I)):
        pdf_url = pdf_link["href"]
        if pdf_url.startswith("//"):
            pdf_url = "https:" + pdf_url
        elif pdf_url.startswith("/"):
            pdf_url = "https://www.nirfindia.org" + pdf_url

        # Walk up to the row/container holding this PDF link, then pull
        # all the text nearby -- institute id, name, scores, city, state,
        # overall score, rank all sit within a few ancestor levels.
        container = pdf_link
        text_blob = ""
        for _ in range(6):  # climb up a handful of levels
            if container.parent is None:
                break
            container = container.parent
            text_blob = container.get_text(" ", strip=True)
            # Stop climbing once we've captured enough context (both the
            # institute code and a numeric score should be present)
            if re.search(r"IR-[A-Z]-[A-Z]-\d+", text_blob) and re.search(r"\d+\.\d{2}", text_blob):
                break

        id_match = re.search(r"(IR-[A-Z]-[A-Z]-\d+)", text_blob)
        institute_id = id_match.group(1) if id_match else None

        # TLR (100) | RPC (100) | GO (100) | OI (100) | PERCEPTION (100)
        # followed by five decimal scores in the same order.
        score_labels = re.findall(r"(TLR|RPC|GO|OI|PERCEPTION)\s*\(100\)", text_blob)
        score_values = re.findall(r"\d{1,3}\.\d{2}", text_blob)

        tlr = rpc = go = oi = pr = overall = None
        rank = None
        if len(score_values) >= 6:
            # first 5 decimals = sub-scores in the labelled order,
            # 6th = overall score. Rank is the integer right after it.
            tlr, rpc, go, oi, pr = score_values[:5]
            overall = score_values[5]
            rank_match = re.search(re.escape(overall) + r"\s*\|?\s*(\d+)", text_blob)
            if rank_match:
                rank = rank_match.group(1)

        name_match = re.search(r"IR-[A-Z]-[A-Z]-\d+\s*\|?\s*([A-Za-z][^|]{3,120}?)\s*(?:\[|More Details)", text_blob)
        name = name_match.group(1).strip() if name_match else pdf_link.get_text(strip=True) or None

        # City/State: NIRF renders this as one unbroken string, e.g.
        # "New Delhi Delhi" (city="New Delhi", state="Delhi") or
        # "Bengaluru Karnataka". Match a known state name at the end of
        # the segment rather than guessing from word count -- see
        # INDIAN_STATES_UTS above.
        city = state = None
        if overall:
            seg_match = re.search(r"\d{1,3}\.\d{2}\s+([A-Za-z][A-Za-z .]+?)\s+" + re.escape(overall), text_blob)
            if seg_match:
                segment = seg_match.group(1).strip()
                for st in INDIAN_STATES_UTS:
                    if segment.endswith(st):
                        state = st
                        city = segment[:-len(st)].strip() or st
                        break
                if state is None:
                    # fallback: last word as state, rest as city (best effort
                    # if a state/UT name isn't in the list above)
                    parts = segment.rsplit(" ", 1)
                    city, state = (parts[0], parts[1]) if len(parts) == 2 else (segment, None)

        if institute_id:
            rows.append({
                "year": year, "institute_id": institute_id, "name": name,
                "city": city, "state": state,
                "tlr_score": tlr, "rpc_score": rpc, "go_score": go,
                "oi_score": oi, "pr_score": pr,
                "overall_score": overall, "rank": rank,
                "pdf_url": pdf_url,
            })

    # De-duplicate: the same institution can appear once per rank-band page
    # if pages overlap, and each PDF link only occurs once per row anyway.
    seen = set()
    unique_rows = []
    for r in rows:
        key = (r["institute_id"], r["year"])
        if key not in seen:
            seen.add(key)
            unique_rows.append(r)
    return unique_rows


def scrape_listing_for_year(year: int, category: str) -> list[dict]:
    all_rows: dict[str, dict] = {}
    for suffix in PAGE_SUFFIXES:
        found_new = False
        for url in listing_url_candidates(year, category, suffix):
            cache_name = re.sub(r"\W+", "_", url) + ".html"
            html = fetch_cached(url, HTML_CACHE / cache_name)
            if html is None:
                continue
            rows = parse_listing_html(html, year, category)
            for r in rows:
                if r["institute_id"] not in all_rows:
                    all_rows[r["institute_id"]] = r
                    found_new = True
            if rows:
                break  # this suffix worked under this URL pattern, don't also try the other pattern
        if not found_new and suffix != "":
            # ran out of rank-band pages for this year/category
            break
    log.info("Year %d (%s): found %d institutions across listing pages", year, category, len(all_rows))
    return list(all_rows.values())


# --------------------------------------------------------------------------
# Individual institution PDF parsing
# --------------------------------------------------------------------------

def _grab_three_year_ints(text: str, label: str) -> tuple:
    """
    Many fields in these PDFs are laid out as:
        <Label> <val_y1> <val_y2> <val_y3>
    with y1 = most recent year. Returns (val_y1, val_y2, val_y3) as strings,
    or (None, None, None) if the label isn't found.
    """
    m = re.search(re.escape(label) + r"\s*(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)", text)
    if m:
        return tuple(v.replace(",", "") for v in m.groups())
    return (None, None, None)


def extract_student_strength(pdf) -> tuple:
    """
    Sums the 'Total Students' column across all program-level rows (UG,
    PG, PG-Integrated, and any others -- program structures vary a lot
    between institutions, e.g. UG can be 3/4/5-year, PG can be 1/2/3-year)
    in the 'Total Actual Student Strength' table.

    Matched by header content (must contain both 'Male' and 'Total
    Students') rather than by section heading text, because a DIFFERENT
    table later in the same document (Ph.D student counts) also has a
    cell literally called 'Total Students' -- matching on the full header
    row avoids picking up that unrelated table by mistake.

    Returns (total: int|None, breakdown: dict) -- breakdown is kept so the
    raw per-program-level numbers are never silently lost even though only
    the total is used for the ratio calculation.
    """
    for page in pdf.pages:
        for table in page.extract_tables():
            if not table or not table[0]:
                continue
            header = table[0]
            header_text = " ".join(h or "" for h in header)
            if "Male" in header_text and "Total Students" in header_text:
                col_idx = next((i for i, h in enumerate(header) if h and "Total Students" in h), None)
                if col_idx is None:
                    continue
                total = 0
                breakdown = {}
                for row in table[1:]:
                    if len(row) > col_idx and row[col_idx] and row[col_idx].strip().isdigit():
                        program = (row[0] or "").replace("\n", " ").strip()
                        count = int(row[col_idx])
                        breakdown[program] = count
                        total += count
                if breakdown:  # only return if we actually matched real rows
                    return total, breakdown
    return None, {}


def parse_institution_pdf(pdf_path: Path) -> dict:
    """
    Extract the fields we care about from one institution's raw-data PDF.
    Anything not found stays None -- the row is still written, just with
    gaps, and the full "Faculty Details" section text is preserved
    regardless so nothing is silently lost (see the module docstring's
    KNOWN LIMITATION note).
    """
    # Only initialize the fields this function is responsible for -- never
    # LISTING_FIELDS. See the comment above PDF_FIELDS for why this matters.
    result = {f: None for f in PDF_FIELDS}
    result["parse_status"] = "ok"

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            total_students, breakdown = extract_student_strength(pdf)
            if total_students is not None:
                result["total_student_strength"] = total_students
                result["student_strength_breakdown"] = json.dumps(breakdown)
    except Exception as e:
        result["parse_status"] = f"pdf_open_failed: {e}"
        return result

    # Faculty count
    m = re.search(r"Number of faculty members entered\s*(\d+)", full_text)
    if m:
        result["faculty_count"] = m.group(1)

    # Keep the whole "Faculty Details" section onward, in case there's
    # more (e.g. a PhD-qualification breakdown) that this script doesn't
    # yet know how to parse structurally.
    fac_section = re.search(r"Faculty Details(.*)", full_text, re.S)
    if fac_section:
        result["faculty_section_raw"] = fac_section.group(1)[:4000].strip()

    # PhD students currently enrolled: "Full Time 2529Part Time 45"
    # immediately follows "Total Students" under Ph.D Student Details.
    m = re.search(r"Ph\.D Student Details.*?Full Time\s*(\d+)\s*Part Time\s*(\d+)", full_text, re.S)
    if m:
        result["phd_fulltime_current"], result["phd_parttime_current"] = m.groups()

    # PhD graduated, 3 years: "Full Time 278 231 203" then "Part Time 3 0 2"
    m = re.search(
        r"No\. of Ph\.D students graduated.*?Full Time\s*(\d+)\s+(\d+)\s+(\d+)\s*Part Time\s*(\d+)\s+(\d+)\s+(\d+)",
        full_text, re.S,
    )
    if m:
        (result["phd_graduated_fulltime_y1"], result["phd_graduated_fulltime_y2"], result["phd_graduated_fulltime_y3"],
         result["phd_graduated_parttime_y1"], result["phd_graduated_parttime_y2"], result["phd_graduated_parttime_y3"]) = m.groups()

    # Sponsored research: projects / funding agencies / amount, 3 years each
    (result["sponsored_projects_y1"], result["sponsored_projects_y2"], result["sponsored_projects_y3"]) = \
        _grab_three_year_ints(full_text, "Total no. of Sponsored Projects")
    (result["sponsored_funding_agencies_y1"], result["sponsored_funding_agencies_y2"], result["sponsored_funding_agencies_y3"]) = \
        _grab_three_year_ints(full_text, "Total no. of Funding Agencies")
    (result["sponsored_amount_y1"], result["sponsored_amount_y2"], result["sponsored_amount_y3"]) = \
        _grab_three_year_ints(full_text, "Total Amount Received (Amount in Rupees)")

    # Flag rows where almost nothing matched -- likely a layout this
    # script hasn't seen yet, worth a manual look rather than trusting silently.
    matched_fields = sum(
        1 for k in ("faculty_count", "phd_fulltime_current", "sponsored_projects_y1")
        if result.get(k) is not None
    )
    if matched_fields == 0:
        result["parse_status"] = "no_fields_matched_check_layout"

    return result


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def already_in_csv() -> set:
    """(institute_id, year) pairs already written, so re-runs can skip them."""
    done = set()
    if CSV_PATH.exists():
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row["institute_id"], row["year"]))
    return done


def append_row(row: dict):
    write_header = not CSV_PATH.exists()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k) for k in CSV_FIELDS})


def log_failure(institute_id: str, year: int, reason: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(FAIL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{year}\t{institute_id}\t{reason}\n")


def run(years: list[int], category: str):
    done = already_in_csv()
    for year in years:
        listing_rows = scrape_listing_for_year(year, category)
        for row in listing_rows:
            key = (row["institute_id"], str(year))
            if key in done:
                continue

            pdf_cache_name = f"{year}_{category}_{row['institute_id']}.pdf"
            pdf_path = PDF_CACHE / pdf_cache_name
            pdf_bytes = fetch_cached(row["pdf_url"], pdf_path)
            if pdf_bytes is None:
                log.warning("Could not fetch PDF for %s (%d)", row["institute_id"], year)
                log_failure(row["institute_id"], year, "pdf_fetch_failed")
                row.update({f: None for f in CSV_FIELDS if f not in row})
                row["parse_status"] = "pdf_fetch_failed"
                append_row(row)
                continue

            parsed = parse_institution_pdf(pdf_path)
            row.update(parsed)
            append_row(row)
            if row["parse_status"] != "ok":
                log_failure(row["institute_id"], year, row["parse_status"])

            log.info("Done: %d %s (%s) -- status=%s", year, row["institute_id"], row.get("name"), row["parse_status"])

    log.info("Finished. Results in %s, failures logged in %s", CSV_PATH, FAIL_LOG_PATH)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape NIRF University-category data.")
    parser.add_argument("--years", type=int, nargs="+", required=True,
                         help="e.g. --years 2019 2020 2021 2022 2023 2024 2025")
    parser.add_argument("--category", default="University",
                         help="NIRF category name as it appears in the URL, e.g. University, Engineering")
    args = parser.parse_args()
    run(args.years, args.category)