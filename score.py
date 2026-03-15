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

CRITICAL SCOPE: This score measures ONLY *cognitive/digital* AI exposure — \
how much language models, AI agents, and digital automation will reshape the \
knowledge-work and information-processing components of this occupation. \
Do NOT factor in industrial robotics, autonomous vehicles, or physical \
automation machinery. Those are a separate dimension. A welder scores low \
even though welding robots exist; a truck driver scores low even though \
autonomous vehicles are coming. Focus only on whether AI software changes \
the cognitive tasks of the job.

AI Exposure measures: how much will cognitive AI (LLMs, agents, RPA, \
generative AI) reshape this occupation? Consider both direct effects (AI \
doing the cognitive/digital work) and indirect effects (AI making each \
worker so productive that fewer are needed for the same output).

The key signal is whether the job's work product is fundamentally digital. \
If the job can be done entirely from a home office on a computer — writing, \
coding, analyzing, communicating — then AI exposure is inherently high (7+), \
because AI capabilities in digital domains are advancing rapidly. Conversely, \
jobs requiring physical presence, manual skill, or real-time human presence \
in the physical world have a natural barrier to cognitive AI exposure.

Use these Canadian-calibrated anchors:

- **0–1: Minimal.** Almost entirely physical, hands-on, or unpredictable \
field work. AI has essentially no impact on the daily core tasks. \
Examples: roofer, landscaper, commercial diver, underground miner, \
oil field worker.

- **2–3: Low.** Mostly physical or interpersonal work. AI might assist with \
minor paperwork or scheduling but doesn't touch the core job. \
Examples: electrician, plumber, firefighter, dental hygienist, welder, \
heavy equipment operator, forest harvesting worker.

- **4–5: Moderate.** A blend of physical/interpersonal and knowledge work. \
AI meaningfully assists the information-processing parts but a substantial \
share still requires human presence. \
Examples: registered nurse, police officer, veterinarian, social worker, \
secondary school teacher, construction manager.

- **6–7: High.** Predominantly knowledge work with some need for human \
judgment, relationships, or physical presence. AI tools already provide \
significant productivity gains. \
Examples: financial advisor, accountant, journalist, college professor, \
HR manager, business analyst, family lawyer.

- **8–9: Very high.** Job is almost entirely done on a computer. Core tasks \
— writing, coding, analyzing, designing, communicating — are all domains \
where AI is rapidly improving. Major restructuring likely. \
Examples: software developer, graphic designer, translator, paralegal, \
data analyst, technical writer, copywriter, web designer.

- **10: Maximum.** Routine information processing, fully digital, no \
physical component. AI can already do most of it today. \
Examples: data entry clerk, telemarketer, routine transcription roles.

In your rationale, be specific about which tasks within the Canadian context \
drive the score. Reference whether the occupation involves digital-first work \
or physical/interpersonal work that limits AI exposure. If the occupation has \
high physical automation (robotics) risk but low cognitive AI exposure, \
explicitly acknowledge this distinction so readers understand the occupation \
may still face technological displacement through a different mechanism.

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
