"""Generate data/employees.csv: 300 FICTIONAL demo employees with leave balances.

Run from ~/hrbot:   python scripts/make_employees.py

Balances follow the Leave Policy (NTL/HR/POL/001), as of AS_OF, in Leave Year 2026-27:
- Table 1: annual EL / CL / SL by Grade, and the EL accumulation limit.
- EL is credited monthly in advance on the 1st, at 1/12 of the annual entitlement (Clause 3.2);
  a joiner on or before the 15th earns that month (Annexure D.2).
- CL and SL are credited in full on 1 April, prorated for joiners in the year and rounded down
  to the nearest half day (Annexure D.2). CL lapses on 31 March; SL carries forward up to 24 days.
- EL carried forward from earlier years is capped at the Grade's accumulation limit.
Leave already taken is random but seeded, so the file is identical on every run.
All names are invented combinations; any resemblance to a real person is coincidental.
"""
import csv
import math
import random
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "employees.csv"
AS_OF = date(2026, 9, 28)
LEAVE_YEAR_START = date(2026, 4, 1)
SEED = 20260928

GRADES = {  # grade: (designation, EL, CL, SL, EL accumulation limit)  - Leave Policy Table 1
    "L1": ("Trainee", 12, 6, 8, 30),
    "L2": ("Associate", 18, 7, 8, 45),
    "L3": ("Software Engineer", 18, 7, 8, 45),
    "L4": ("Senior Software Engineer", 18, 7, 8, 45),
    "L5": ("Technical Lead", 21, 7, 8, 45),
    "L6": ("Manager", 21, 7, 8, 45),
    "L7": ("Senior Manager", 24, 7, 8, 60),
    "L8": ("Director", 24, 7, 8, 60),
}
GRADE_MIX = {"L1": 30, "L2": 60, "L3": 70, "L4": 55, "L5": 40, "L6": 25, "L7": 13, "L8": 7}
MIN_YEARS = {"L1": 0, "L2": 0.5, "L3": 1, "L4": 3, "L5": 5, "L6": 7, "L7": 10, "L8": 13}
LOCATIONS = {"Bengaluru": 40, "Pune": 18, "Hyderabad": 17, "Chennai": 14, "Noida": 11}
SL_CARRY_LIMIT = 24
FIRST = ("Aarav Aditi Akash Ananya Arjun Bhavana Chetan Deepa Devika Farhan Gaurav Harini Ishaan Jaya "
         "Karthik Kavya Lakshmi Manish Meera Naveen Neha Nikhil Pooja Pranav Priya Rahul Riya Rohan "
         "Sahana Sameer Sanjana Shreya Siddharth Sneha Suresh Tanvi Varun Vidya Vikram Yash Zoya Omkar "
         "Irfan Anjali Kunal Divya Rajesh Swati Abhishek Nandini").split()
LAST = ("Rao Iyer Sharma Patil Reddy Nair Kulkarni Menon Gupta Deshpande Pillai Joshi Verma Shetty "
        "Banerjee Chatterjee Kapoor Mehta Naidu Bhat Hegde Mishra Saxena Srinivasan Krishnan Qureshi "
        "Fernandes D'Souza Das Agarwal").split()
# Demo sign-in accounts shown in the app: the first employee with each (grade, location) below,
# so the demo covers several grades and all five locations.
DEMO_SLOTS = [("L3", "Bengaluru"), ("L2", "Pune"), ("L5", "Hyderabad"), ("L4", "Noida"), ("L7", "Chennai")]


def half_down(x):
    return math.floor(x * 2) / 2


def months_credited(join: date) -> int:
    """EL months credited in this Leave Year up to AS_OF (credit on the 1st, in advance)."""
    start = max(join, LEAVE_YEAR_START)
    first = (start.year, start.month) if start.day <= 15 else (start.year + (start.month == 12), start.month % 12 + 1)
    last = (AS_OF.year, AS_OF.month)
    return max(0, (last[0] - first[0]) * 12 + last[1] - first[1] + 1)


def main():
    rng = random.Random(SEED)
    grades = [g for g, n in GRADE_MIX.items() for _ in range(n)]
    rng.shuffle(grades)
    locs = [loc for loc, n in LOCATIONS.items() for _ in range(n)]
    names = set()
    rows = []
    for k, grade in enumerate(grades):
        eid = f"NXR{100001 + k}"
        while True:
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            if name not in names:
                names.add(name)
                break
        desig, el_year, cl_year, sl_year, el_limit = GRADES[grade]
        years = MIN_YEARS[grade] + rng.uniform(0, 4)
        join = date.fromordinal(AS_OF.toordinal() - int(years * 365.25) - rng.randint(0, 20))
        if join > AS_OF:
            join = AS_OF
        joined_this_year = join >= LEAVE_YEAR_START
        # carried forward from earlier years: unused EL, capped at the accumulation limit
        prior_years = max(0.0, (LEAVE_YEAR_START - join).days / 365.25)
        el_open = 0.0 if joined_this_year else min(el_limit, half_down(prior_years * el_year * rng.uniform(0.15, 0.45)))
        el_accrued = round(el_year / 12 * months_credited(join), 1)
        if joined_this_year:
            frac = months_credited(join) / 12
            cl_credit, sl_credit = half_down(cl_year * frac), half_down(sl_year * frac)
            sl_open = 0.0
        else:
            cl_credit, sl_credit = float(cl_year), float(sl_year)
            sl_open = min(SL_CARRY_LIMIT - sl_year, half_down(prior_years * rng.uniform(0, 3)))
        el_taken = half_down(rng.uniform(0, 0.8) * (el_open + el_accrued))
        cl_taken = half_down(rng.uniform(0, 0.7) * cl_credit)
        sl_taken = half_down(rng.uniform(0, 0.5) * (sl_open + sl_credit))
        rows.append({
            "employee_id": eid, "name": name, "grade": grade, "designation": desig,
            "location": rng.choice(locs), "join_date": join.isoformat(),
            "el_opening": el_open, "el_accrued": el_accrued, "el_taken": el_taken,
            "el_balance": round(el_open + el_accrued - el_taken, 1),
            "cl_credited": cl_credit, "cl_taken": cl_taken, "cl_balance": cl_credit - cl_taken,
            "sl_opening": sl_open, "sl_credited": sl_credit, "sl_taken": sl_taken,
            "sl_balance": sl_open + sl_credit - sl_taken,
            "rh_balance": rng.choice([2, 2, 1, 0]), "as_of": AS_OF.isoformat(),
            "demo_account": "no",
        })
    for grade, loc in DEMO_SLOTS:
        next(r for r in rows if r["grade"] == grade and r["location"] == loc)["demo_account"] = "yes"
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="") as f:
        f.write("# DEMO DATA - fictional employees of the fictional Nexora Technologies Limited (college project)\n")
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    by_grade = {g: sum(r["grade"] == g for r in rows) for g in GRADES}
    print(f"Wrote {len(rows)} employees to {OUT.relative_to(ROOT)}; by grade {by_grade}")
    for r in rows:
        if r["demo_account"] == "yes":
            print(f"  demo: {r['employee_id']} {r['name']:<20} {r['grade']} {r['location']:<10} joined {r['join_date']} "
                  f"EL {r['el_balance']} CL {r['cl_balance']} SL {r['sl_balance']}")
    bad = [r["employee_id"] for r in rows if min(r["el_balance"], r["cl_balance"], r["sl_balance"]) < 0]
    print("negative balances:", bad or "none")


if __name__ == "__main__":
    main()
