"""
Quick sanity check for candidate affilnames BEFORE updating the confirmed
CSV and running a full 5-year retry. Costs one API call per candidate --
much cheaper than discovering a guess was wrong after a full pull.

Usage:
    python3 verify_candidate_names.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("SCOPUS_API_KEY")
INST_TOKEN = os.getenv("SCOPUS_INST_TOKEN") or None

HEADERS = {"X-ELS-APIKey": API_KEY, "Accept": "application/json"}
if INST_TOKEN:
    HEADERS["X-ELS-Insttoken"] = INST_TOKEN

CANDIDATES = [
    ("NMIMS (spelling fix)", 'AFFIL("Shri Vile Parle Kelavani Mandal\'s Narsee Monjee Institute of Management Studies")'),
    ("NMIMS (short form)", 'AFFIL("NMIMS University")'),
    ("Tamil Nadu Veterinary (with 'and')", 'AFFIL("Tamil Nadu Veterinary and Animal Sciences University")'),
    ("Amity Haryana (full name)", 'AFFIL("Amity University Haryana")'),
]


def check(label: str, query: str):
    resp = requests.get(
        "https://api.elsevier.com/content/search/scopus",
        headers=HEADERS,
        params={"query": f"{query} AND PUBYEAR = 2023", "count": 3},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"{label}: HTTP {resp.status_code} -- {resp.text[:150]}")
        return
    data = resp.json().get("search-results", {})
    total = data.get("opensearch:totalResults", "0")
    print(f"{label}: {total} results for 2023" + (" -- LOOKS REAL, worth using" if int(total) > 20 else " -- still low/zero, try another variant"))


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: SCOPUS_API_KEY not set in .env")
    else:
        for label, query in CANDIDATES:
            check(label, query)