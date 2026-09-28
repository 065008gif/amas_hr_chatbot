# Answer evaluation (single questions)

Scored 6 of 119 items. String checks against gold facts (tests/eval_set.yaml); no model is used as a judge.

| Metric | Result |
|---|---|
| answerable accuracy | 1/2 (50.0%) |
| answerable correct or partly | 2/2 (100.0%) |
| citation snippet on cited page | 9/9 (100.0%) |
| correct answers citing a gold page | 2/2 (100.0%) |
| refusal precision | 1/1 (100.0%) |
| refusal recall | 1/1 (100.0%) |
| escalation recall | 0/2 (0.0%) |
| clarify rate | 1/1 (100.0%) |

## By category

| Category | clarify_ok | correct | correctly_refused | missed_escalation | partly |
|---|---|---|---|---|---|
| circular | 0 | 1 | 0 | 0 | 1 |
| clarify | 1 | 0 | 0 | 0 | 0 |
| escalation | 0 | 0 | 0 | 2 | 0 |
| unanswerable | 0 | 0 | 1 | 0 | 0 |

## Items not fully correct

- **T01** (circular, partly, route answer, expected answer): How many days of paternity leave do I get for a baby born in August 2025?  
  Answer: You are entitled to 10 Working Days of paternity leave for a baby born in August 2025 [S1][S2].
- **E03** (escalation, missed_escalation, route answer, expected escalate/tool): My salary for August has still not been credited. What should I do?  
  Answer: Salary is credited on the last Working Day of each month, and any payroll issues should be raised as a ticket in the Payroll category within 30 days of the pay date; the team will correct it in the next payroll cycle [S2].
- **E10** (escalation, missed_escalation, route answer, expected escalate): A colleague keeps making jokes about my caste in team meetings.  
  Answer: You can raise a complaint about the caste‑based jokes with the Internal Committee, or first speak confidentially to the HR Business Partner for guidance. Such remarks are prohibited as discrimination under the Code of Conduct and Ethics and qualify as harassment under the POSH policy’s definition of
