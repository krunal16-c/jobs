"""
Build a compact JSON for the Canadian website by merging CSV stats with AI exposure scores.

Reads occupations.csv (for stats) and scores.json (for AI exposure).
Writes site/data.json.

Usage:
    uv run python build_site_data_ca.py
"""

import csv
import json
import os


def main():
    # Load AI exposure scores
    scores = {}
    if os.path.exists("scores.json"):
        with open("scores.json") as f:
            scores_list = json.load(f)
        scores = {s["slug"]: s for s in scores_list}

    # Load CSV stats
    with open("occupations.csv") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Load scraped Job Bank data (titles + requirements) keyed by slug
    jb_data = {}
    if os.path.exists("occupations.json"):
        with open("occupations.json") as f:
            occ_list = json.load(f)
        jb_data = {o["slug"]: o for o in occ_list}

    # Merge
    data = []
    for row in rows:
        slug = row["slug"]
        score = scores.get(slug, {})
        jb = jb_data.get(slug, {})
        data.append({
            "title": row["title"],
            "title_jobbank": jb.get("title_jobbank") or None,
            "slug": slug,
            "noc_code": row.get("noc_code", ""),
            "category": row["category"],
            "pay": int(row["median_pay_annual"]) if row["median_pay_annual"] else None,
            "jobs": int(row["num_jobs_2023"]) if row["num_jobs_2023"] else None,
            "outlook": int(row["outlook_pct"]) if row["outlook_pct"] else None,
            "outlook_desc": row["outlook_desc"],
            "education": row["entry_education"],
            "education_req": jb.get("education_req") or None,
            "exposure": score.get("exposure"),
            "exposure_rationale": score.get("rationale"),
            "url": row.get("url", ""),
        })

    os.makedirs("site", exist_ok=True)
    with open("site/data.json", "w") as f:
        json.dump(data, f)

    print(f"Wrote {len(data)} occupations to site/data.json")
    total_jobs = sum(d["jobs"] for d in data if d["jobs"])
    print(f"Total jobs represented: {total_jobs:,}")
    scored = sum(1 for d in data if d["exposure"] is not None)
    print(f"Occupations with AI exposure scores: {scored}/{len(data)}")


if __name__ == "__main__":
    main()
