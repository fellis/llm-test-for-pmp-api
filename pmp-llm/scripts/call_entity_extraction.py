#!/usr/bin/env python3
"""Build entity extraction payload (1 handle) for POST /v1/chat/completions."""

import json
import sys

SYSTEM = r"""You are a commercial entity extraction engine.

Your task:
From the given list of handles, independently identify REAL, well-known,
profit-oriented companies that are commercially related to the
function, role, activity, or product implied by EACH handle.

IMPORTANT:
- Treat EACH handle independently
- Your goal is MAXIMUM COVERAGE of real company names
- Include ANY relevant commercial entities:
  product owners, service providers, platforms, intermediaries, consultancies,
  staffing firms, marketplaces, vendors
- Banks, lenders, and large enterprises ARE ALLOWED
- Prefer recall over precision

CRITICAL OUTPUT RULES:
- Output ONLY company handles
- One company per line
- Lowercase only
- NO explanations
- NO headers
- NO grouping
- NO empty lines: every line must be exactly one company name. Do not insert blank lines anywhere.
- NO placeholders
- NEVER output words like "none", "n/a", or similar
- NEVER output the input handle itself
- NEVER invent brand-like names
- If a handle has no relevant companies, output NOTHING for it

Company validity rules:
- Company names must be real and widely recognized
- Do not output generic nouns or categories
- Do not output fictional or guessed brands
- No legal suffixes (inc, ltd, gmbh, sa, etc.)

Example of valid format (one company per line, no blank lines between):
company1
company2
company3

The final output must be a single continuous list: one company name per line, no empty lines.
"""


def main():
    handle = sys.argv[1] if len(sys.argv) > 1 else "adi-moped"
    user = "Extract company names related to the following handles\n(one handle per line):\n\n" + handle
    payload = {
        "model": "llm",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "max_tokens": 600,
        "temperature": 0,
    }
    out_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/entity_payload.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(out_path)


if __name__ == "__main__":
    main()
