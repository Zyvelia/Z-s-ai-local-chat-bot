"""Offline regression evaluation for deterministic dialogue-quality heuristics.

Run: cd backend && python evaluations/run_local_quality.py
No Ollama, credentials, network, or database is required.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.quality import quality_evaluation  # noqa: E402


def main() -> int:
    cases = json.loads((Path(__file__).with_name('local_quality_cases.json')).read_text())
    failures = []
    for case in cases:
        result = quality_evaluation(case['reply'], case['prior'], case['character'])
        ok = result['possibly_repetitive'] is case['expect_repetitive']
        print(f"{'PASS' if ok else 'FAIL'} {case['id']}: similarity={result['repetition_similarity']:.3f}")
        if not ok:
            failures.append(case['id'])
    print(f'{len(cases)-len(failures)}/{len(cases)} cases passed (heuristic evaluation)')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
