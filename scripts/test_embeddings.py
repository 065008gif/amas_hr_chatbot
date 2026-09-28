"""Phase 1, Step 5: can the embedding model be downloaded and run here, and how fast is it?

Usage: python scripts/test_embeddings.py
The model is cached inside ~/hrbot/.cache/ (git-ignored), never in the home directory.
"""
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
os.environ.setdefault("HF_HOME", str(CACHE / "huggingface"))  # keep HF files inside ~/hrbot

from fastembed import TextEmbedding  # noqa: E402

MODEL = "BAAI/bge-small-en-v1.5"

# 100 synthetic HR-style chunks (about 300 tokens each), varied so they are not identical.
TOPICS = [
    ("Paternity Leave", "A male employee shall be entitled to paternity leave of {n} working days, to be availed within six months of the birth or adoption of a child."),
    ("Earned Leave", "Earned Leave shall accrue at the rate of {n} days per completed month of service and may be accumulated up to a maximum prescribed for the grade."),
    ("Notice Period", "An employee in grade L{g} who resigns shall serve a notice period of {n} days, which may be waived in whole or in part at the sole discretion of the Business Unit Head."),
    ("Airport Cab", "Employees in grade L{g} and above may claim an airport cab up to Rs. {n}00 per trip, subject to submission of the original receipt through the Nexora People Portal."),
    ("Gratuity", "Gratuity shall be payable to an employee who has rendered continuous service of not less than five years, calculated at fifteen days' wages for each completed year."),
    ("Hybrid Work", "Employees may work from home for up to {n} days in a calendar week with the prior approval of the reporting manager, save as provided in Annexure C."),
    ("POSH Complaint", "A complaint of sexual harassment may be made in writing to the Internal Committee within {n} months from the date of the incident."),
    ("Hotel Cap", "The hotel entitlement for grade L{g} in metro cities shall not exceed Rs. {n},000 per night, inclusive of taxes, unless approved by the Travel Desk."),
    ("Gifts", "No employee shall accept any gift exceeding Rs. {n},000 in value from a vendor, client or business associate without declaring it to the Ethics Officer."),
    ("BYOD", "Personal devices used for official work must be enrolled in the mobile device management solution within {n} days of joining, as required by the IT Security team."),
]
FILLER = ("This clause shall be read together with the definitions in Section 2 and is subject to the "
          "applicable statutory provisions in force in the State where the employee is based. Requests "
          "must be raised on the Nexora People Portal (NPP) and are approved first by the reporting "
          "manager and thereafter by the HR Business Partner within the turnaround time specified in "
          "the escalation matrix. Notwithstanding anything contained herein, the Company reserves the "
          "right to amend this clause by issuing a circular, which shall prevail over the body text. ")


def build_chunks(n=100):
    chunks = []
    for i in range(n):
        title, rule = TOPICS[i % len(TOPICS)]
        text = (f"Clause {i // 10 + 3}.{i % 10 + 1} {title}. " + rule.format(n=5 + i % 12, g=1 + i % 8)
                + " " + FILLER * 2 + f"Illustration {i}: an employee in grade L{1 + i % 8} based in "
                + ["Bengaluru", "Pune", "Hyderabad", "Chennai", "Noida"][i % 5] + " applies this rule.")
        chunks.append(text)
    return chunks


def main():
    chunks = build_chunks()
    words = sum(len(c.split()) for c in chunks) / len(chunks)
    print(f"Chunks: {len(chunks)}, average {words:.0f} words (about {words * 1.3:.0f} tokens) each")

    t = time.perf_counter()
    model = TextEmbedding(MODEL, cache_dir=str(CACHE / "fastembed"))
    print(f"Model download + load: {time.perf_counter() - t:.1f} s  (cache: .cache/fastembed)")

    t = time.perf_counter()
    vecs = list(model.embed(chunks, batch_size=32))
    print(f"Embed 100 chunks (first run): {time.perf_counter() - t:.2f} s")
    t = time.perf_counter()
    vecs = list(model.embed(chunks, batch_size=32))
    print(f"Embed 100 chunks (second run): {time.perf_counter() - t:.2f} s")
    print(f"Vector size: {len(vecs[0])} numbers per chunk")

    t = time.perf_counter()
    q = list(model.query_embed(["How many days of paternity leave do I get?"]))[0]
    print(f"Embed one query: {(time.perf_counter() - t) * 1000:.0f} ms")

    # Sanity check: vectors are normalised, so the dot product = cosine similarity.
    scores = sorted(((float(q @ v), i) for i, v in enumerate(vecs)), reverse=True)[:3]
    print("Top 3 matches for 'How many days of paternity leave do I get?':")
    for s, i in scores:
        print(f"  score {s:.3f}  chunk {i:3d}: {chunks[i][:70]}...")
    ok = all(TOPICS[i % len(TOPICS)][0] == "Paternity Leave" for _, i in scores)
    print("Sanity check:", "PASS (all top 3 are paternity-leave chunks)" if ok else "FAIL")


if __name__ == "__main__":
    main()
