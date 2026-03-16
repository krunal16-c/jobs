"""
Score each occupation's AI exposure using an LLM via OpenAI.

Reads Markdown descriptions from pages/, sends each to an LLM with a scoring
rubric, and collects structured scores. Results are cached incrementally to
scores.json so the script can be resumed if interrupted.

Usage:
    uv run python score.py
    uv run python score.py --model gpt-4o
    uv run python score.py --start 0 --end 10   # test on first 10
"""

import argparse
import json
import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gpt-4o-mini"
OUTPUT_FILE = "scores.json"
API_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = """\
You are an expert analyst evaluating how exposed different occupations are to \
AI for a Canadian labour market study. You will be given a description of a \
Canadian occupation from the National Occupational Classification (NOC) 2021 \
system, including employment statistics from the Canadian Occupational \
Projection System (COPS 2024–2033).

Rate the occupation's **AI Exposure** on a scale from 0 to 10.

CRITICAL SCOPE: This score measures *cognitive/digital* AI exposure only — \
NOT industrial robots, autonomous vehicles, or physical automation machinery. \
A welder scores low even though welding robots exist; a truck driver scores \
low even though autonomous vehicles are coming. Focus on whether AI software \
changes the cognitive, communication, and coordination tasks of the job.

The AI landscape to assess includes all three tiers:
1. **Base LLMs** — writing, summarising, drafting, analysing, coding, \
translating.
2. **LLM + tools** — AI with access to APIs, calendars, email, databases, \
search, forms, and CRMs. This tier can already handle: scheduling appointments, \
booking travel, processing expense reports, drafting and sending correspondence, \
filling out forms, answering customer queries, generating reports from databases.
3. **Multi-agent systems** — networks of AI agents that hand off tasks to each \
other and run entire workflows end-to-end with minimal human involvement. \
Examples: an agent that receives a client intake, drafts a contract, schedules \
a signing, and files the document — or a recruiting agent that screens \
résumés, sends interview invitations, and books calendars automatically.

IMPORTANT: Tier 2 and Tier 3 significantly raise exposure for occupations \
whose core value is *coordination, scheduling, communication, and \
routine decision-making* — even when those tasks seem human-facing. \
A receptionist who spends 80% of their day scheduling appointments and \
answering routine queries is highly exposed even if the work feels \
interpersonal. A travel agent whose job is searching options and booking \
itineraries is highly exposed even if the work feels service-oriented.

Use these Canadian-calibrated anchors:

- **0–1: Minimal.** Almost entirely physical, hands-on, or unpredictable \
field work with no meaningful digital coordination component. \
Examples: roofer, landscaper, commercial diver, underground miner, \
oil field worker, logging machine operator.

- **2–3: Low.** Core work is physical or hands-on clinical. AI may assist \
with minor paperwork or scheduling but the dominant value is manual skill \
or physical presence. \
Examples: electrician, plumber, firefighter, welder, heavy equipment \
operator, dental hygienist, forest harvesting worker.

- **4–5: Moderate.** A genuine blend of physical/interpersonal work and \
knowledge/coordination work. AI handles a meaningful portion of the \
administrative and communication tasks but human presence and judgment \
remain central. \
Examples: registered nurse, police officer, veterinarian, social worker, \
secondary school teacher, construction manager, physiotherapist.

- **6–7: High.** Predominantly knowledge work, coordination, or \
communication. AI tools and LLM+tools agents already deliver significant \
productivity gains and are beginning to automate entire sub-tasks. \
Human judgment, client trust, or regulatory accountability remain relevant \
but are under pressure. \
Examples: financial advisor, accountant, journalist, college professor, \
HR manager, business analyst, family lawyer, insurance broker, \
real estate agent, travel counsellor, medical office administrator.

- **8–9: Very high.** Job is almost entirely digital — writing, coding, \
analysing, designing, scheduling, communicating, or coordinating. Core tasks \
are squarely in the domain where LLMs, LLM+tools, and multi-agent systems \
are rapidly improving. Major restructuring likely within 5 years. \
Examples: software developer, graphic designer, translator, paralegal, \
data analyst, technical writer, copywriter, web designer, \
executive assistant, legal administrative assistant, medical transcriptionist, \
claims examiner, procurement and purchasing officer.

- **10: Maximum.** Routine information processing, scheduling, or \
coordination that is fully digital and highly repetitive. Multi-agent \
systems can already handle the entire workflow with near-zero human \
involvement for the core tasks. \
Examples: data entry clerk, telemarketer, appointment scheduler, \
routine transcription roles, basic customer service representative.

In your rationale, be specific about which tasks drive the score. \
Explicitly assess whether Tier 2 (LLM+tools) or Tier 3 (multi-agent \
automation) changes the exposure relative to base-LLM assessment alone. \
If the occupation has high physical automation (robotics) risk but low \
cognitive AI exposure, acknowledge this so readers understand the occupation \
may face displacement through a different mechanism.

Respond with ONLY a JSON object in this exact format, no other text:
{
  "exposure": <0-10>,
  "rationale": "<2-3 sentences explaining the key factors driving the score>"
}\
"""


def score_occupation(client, text, model):
    """Send one occupation to the LLM and parse the structured response."""
    response = client.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0.2,
        },
        timeout=60,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # remove first line
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    return json.loads(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--force", action="store_true",
                        help="Re-score even if already cached")
    args = parser.parse_args()

    with open("occupations.json") as f:
        occupations = json.load(f)

    subset = occupations[args.start:args.end]

    # Load existing scores
    scores = {}
    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE) as f:
            for entry in json.load(f):
                scores[entry["slug"]] = entry

    print(f"Scoring {len(subset)} occupations with {args.model}")
    print(f"Already cached: {len(scores)}")

    errors = []
    client = httpx.Client()

    for i, occ in enumerate(subset):
        slug = occ["slug"]

        if slug in scores:
            continue

        md_path = f"pages/{slug}.md"
        if not os.path.exists(md_path):
            print(f"  [{i+1}] SKIP {slug} (no markdown)")
            continue

        with open(md_path) as f:
            text = f.read()

        print(f"  [{i+1}/{len(subset)}] {occ['title']}...", end=" ", flush=True)

        try:
            result = score_occupation(client, text, args.model)
            scores[slug] = {
                "slug": slug,
                "title": occ["title"],
                **result,
            }
            print(f"exposure={result['exposure']}")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(slug)

        # Save after each one (incremental checkpoint)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(list(scores.values()), f, indent=2)

        if i < len(subset) - 1:
            time.sleep(args.delay)

    client.close()

    print(f"\nDone. Scored {len(scores)} occupations, {len(errors)} errors.")
    if errors:
        print(f"Errors: {errors}")

    # Summary stats
    vals = [s for s in scores.values() if "exposure" in s]
    if vals:
        avg = sum(s["exposure"] for s in vals) / len(vals)
        by_score = {}
        for s in vals:
            bucket = s["exposure"]
            by_score[bucket] = by_score.get(bucket, 0) + 1
        print(f"\nAverage exposure across {len(vals)} occupations: {avg:.1f}")
        print("Distribution:")
        for k in sorted(by_score):
            print(f"  {k}: {'█' * by_score[k]} ({by_score[k]})")


if __name__ == "__main__":
    main()
