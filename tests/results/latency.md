# Live-site latency (https://nexora-hr-portal.vercel.app, measured from the college PC)

| Measurement | Result |
|---|---|
| Cold start: first request until the backend is ready (fresh instance confirmed by server uptime) | median 45.77 s, p95 45.85 s, max 45.85 s (n=2) |
| Probes whose instance had started before the probe (see notes below) | median 64.93 s, p95 64.93 s, max 64.93 s (n=1) |
| Chat answer, cache miss, as the user waits (network included) | median 3.11 s, p95 3.54 s, max 4.12 s (n=20) |
| Chat answer, cache miss, server time only | median 2.87 s, p95 3.28 s, max 3.88 s (n=20) |
| Chat answer, repeated question (cache hit) | median 0.24 s, p95 0.25 s, max 0.25 s (n=5) |
| Page and PDF loads | median 0.36 s, p95 0.61 s, max 0.61 s (n=4) |
| Chat requests that failed | 0 |

Cold probes:

- 2026-09-29T02:07:18: 64.93 s, fresh instance: False (server uptime 122 s, in-function warm-up 4.19 s, separate DNS lookup not timed); idle before: unknown (first probe after the user's push)
- 2026-09-29T02:31:15: 45.85 s, fresh instance: True (server uptime 5 s, in-function warm-up 4.24 s, separate DNS lookup 0.08 s); idle before: 20 min with no requests from this evaluation
- 2026-09-29T03:12:01: 45.69 s, fresh instance: True (server uptime 4 s, in-function warm-up 4.07 s, separate DNS lookup 0.03 s); idle before: 40 min with no requests from this evaluation

The first probe waited 65 s in a single request although its instance had been up for 122 s, so it was not a cold start of that instance; the cause (a second instance starting, or the network) could not be determined, and DNS was not yet timed. The two controlled probes after 20 and 40 idle minutes both reached fresh instances and took about 46 s, of which about 4 s is the backend loading its index and models; the rest is Vercel starting the instance (the Python bundle is 287 MB), before any of our code runs. The portal's waking-up screen waits up to 60 s per attempt, so a first visitor after a quiet period waits about 46 s.
