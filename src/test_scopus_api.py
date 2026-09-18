"""
One-shot diagnostic: does your Scopus API key return real, fully-entitled
data, or is it hitting the "entitlement wall" (authenticated but silently
reduced/empty results because Elsevier doesn't recognize the network)?

Run this BEFORE building/running any larger pipeline -- it costs one API
call and tells you definitively what you're working with.

Setup:
    pip install requests python-dotenv
    cp .env.example .env
    # edit .env, paste your real SCOPUS_API_KEY in

Run (ideally while connected to campus Wi-Fi / your institution's VPN):
    python3 test_scopus_api.py
"""

import os
import sys
import json

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("SCOPUS_API_KEY")
INST_TOKEN = os.getenv("SCOPUS_INST_TOKEN") or None

if not API_KEY:
    print("ERROR: SCOPUS_API_KEY not found. Did you copy .env.example to .env")
    print("and fill in your real key?")
    sys.exit(1)

# A well-known, high-output institution -- if this doesn't return real
# data, nothing will. Using a free-text AFFIL search here (not AF-ID)
# since we haven't done affiliation lookup yet at this stage.
TEST_QUERY = 'AFFIL("Indian Institute of Science") AND PUBYEAR = 2023'

headers = {
    "X-ELS-APIKey": API_KEY,
    "Accept": "application/json",
}
if INST_TOKEN:
    headers["X-ELS-Insttoken"] = INST_TOKEN
    print("Using Insttoken alongside API key.")
else:
    print("No Insttoken set -- relying on network recognition (must be on")
    print("campus Wi-Fi / institutional VPN for this to work).")

print(f"\nQuery: {TEST_QUERY}")
print("Sending request...\n")

resp = requests.get(
    "https://api.elsevier.com/content/search/scopus",
    headers=headers,
    params={"query": TEST_QUERY, "count": 5, "view": "STANDARD"},
    timeout=30,
)

print(f"HTTP status: {resp.status_code}")

if resp.status_code == 401:
    print("\n>>> DIAGNOSIS: Invalid API key. Double check what's in .env")
    print("    (no extra quotes/spaces, key hasn't expired).")
    sys.exit(1)

if resp.status_code == 429:
    print("\n>>> DIAGNOSIS: Quota exceeded for this key. Check your")
    print("    remaining calls on the Elsevier Developer Portal dashboard.")
    sys.exit(1)

if resp.status_code != 200:
    print(f"\n>>> DIAGNOSIS: Unexpected status. Response body below --")
    print("    paste this back so the issue can be diagnosed properly.")
    print(resp.text[:1000])
    sys.exit(1)

data = resp.json()
results = data.get("search-results", {})
total = results.get("opensearch:totalResults", "0")
entries = results.get("entry", [])

print(f"Total results reported: {total}")
print(f"Entries returned in this page: {len(entries)}\n")

if int(total) == 0 or not entries:
    print(">>> DIAGNOSIS: Zero results for a query that should return")
    print("    thousands (IISc publishes ~2,500+ papers/year). This is the")
    print("    entitlement wall -- your key isn't being recognized as")
    print("    covered by a subscription from wherever this script ran.")
    print("    FIX: get an Insttoken from your library's Scopus admin, add")
    print("    it to .env as SCOPUS_INST_TOKEN, and re-run this script.")
    print("    Also try running from campus Wi-Fi if you weren't already.")
    sys.exit(0)

print("Sample entries (title | citedby-count | journal):")
zero_citations = 0
for e in entries:
    title = e.get("dc:title", "(no title)")
    cited = e.get("citedby-count", "MISSING")
    journal = e.get("prism:publicationName", "(no journal)")
    print(f"  - {title[:60]:60s} | citedby-count={cited:>5} | {journal}")
    if cited in ("0", "MISSING", None):
        zero_citations += 1

print()
if zero_citations == len(entries):
    print(">>> DIAGNOSIS: All entries show 0 or missing citation counts.")
    print("    This is suspicious for IISc 2023 papers -- possible partial")
    print("    entitlement. Citation data specifically may need a higher")
    print("    access tier even if basic search works. Flag this before")
    print("    trusting citation-based numbers in the full pipeline.")
else:
    print(">>> DIAGNOSIS: Looks healthy -- real titles, real journals, and")
    print("    non-zero citation counts. Your key is fully entitled from")
    print("    this network. Safe to proceed with the full pipeline.")

print("\nFull raw response saved to test_response.json for inspection.")
with open("test_response.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)