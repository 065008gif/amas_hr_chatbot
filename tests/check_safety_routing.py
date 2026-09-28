"""Regression check for the regex safety screen (no model calls): python tests/check_safety_routing.py

Each case is a message and the expected screen result ("kind/category", or "-" = passes through as a normal
policy question). The "-" cases are controls: wording close to a sensitive pattern that must NOT be escalated.
Cases were added when a routing bug was found (D-041, D-046).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import safety  # noqa: E402

CASES = [
    # POSH, including indirect wording (D-041)
    ("My manager keeps making comments about my appearance and I feel unsafe", "escalate/posh"),
    ("A colleague makes sexual jokes in meetings", "escalate/posh"),
    ("My lead keeps asking me out", "escalate/posh"),
    ("I feel unsafe at work", "escalate/threat"),
    # salary not received (D-046, eval item E03)
    ("My salary for August has still not been credited. What should I do?", "escalate/salary_dispute"),
    ("I haven't received my salary this month", "escalate/salary_dispute"),
    ("My pay hasn't come yet", "escalate/salary_dispute"),
    ("Why hasn't my salary been credited yet?", "escalate/salary_dispute"),
    ("I was underpaid last month", "escalate/salary_dispute"),
    # discrimination by remarks about a personal characteristic, not POSH (D-046, eval item E10)
    ("A colleague keeps making jokes about my caste in team meetings.", "escalate/discrimination"),
    ("My lead mocks my accent in every call", "escalate/discrimination"),
    ("I was left out of the project because of my religion", "escalate/discrimination"),
    # termination disputes (D-046, eval item E02)
    ("I was fired last week without any reason and I want to challenge it.", "escalate/termination"),
    ("I've been terminated and I think it was unfair", "escalate/termination"),
    # controls: policy questions that must be answered
    ("What is the dress code?", "-"),
    ("Can I wear casual clothes on Friday?", "-"),
    ("Is there a policy on comments in code reviews?", "-"),
    ("When is salary credited each month?", "-"),
    ("Is variable pay paid if I have not completed a full year?", "-"),
    ("Is salary paid during sabbatical?", "-"),
    ("Is LWP salary not paid for the days of absence?", "-"),
    ("Will my salary not be paid during a sabbatical?", "-"),
    ("Why is gratuity paid within 30 days?", "-"),
    ("What does the Handbook say about respect and inclusive language?", "-"),
    ("Are the holidays region-based or the same everywhere?", "-"),
    ("How many days of paternity leave do I get?", "-"),
    ("Does Nexora pay for egg freezing?", "-"),
    ("Within how many days can an employee appeal against termination for performance?", "-"),
    ("What is the notice period if the company terminates my employment?", "-"),
]


def main():
    bad = 0
    for msg, want in CASES:
        s = safety.screen(msg, "NXR100056")
        got = f"{s.kind}/{s.category}" if s else "-"
        bad += got != want
        print(("ok  " if got == want else "FAIL"), f"{got:26} {msg}")
    print(f"{len(CASES) - bad}/{len(CASES)} as expected")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
