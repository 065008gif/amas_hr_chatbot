# Answer evaluation (single questions)

Scored 119 of 119 items. String checks against gold facts (tests/eval_set.yaml); no model is used as a judge.

| Metric | Result |
|---|---|
| answerable accuracy | 85/94 (90.4%) |
| answerable correct or partly | 89/94 (94.7%) |
| citation snippet on cited page | 170/170 (100.0%) |
| correct answers citing a gold page | 87/89 (97.8%) |
| refusal precision | 9/11 (81.8%) |
| refusal recall | 9/9 (100.0%) |
| escalation recall | 10/10 (100.0%) |
| clarify rate | 6/6 (100.0%) |

## By category

| Category | clarify_ok | correct | correctly_refused | escalated_ok | partly | wrong | wrongly_refused |
|---|---|---|---|---|---|---|---|
| circular | 0 | 20 | 0 | 0 | 1 | 0 | 1 |
| clarify | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| conflict | 0 | 4 | 0 | 0 | 0 | 0 | 0 |
| definition | 0 | 3 | 0 | 0 | 1 | 0 | 0 |
| direct | 0 | 33 | 0 | 0 | 0 | 0 | 0 |
| escalation | 0 | 0 | 0 | 10 | 0 | 0 | 0 |
| grade | 0 | 21 | 0 | 0 | 2 | 0 | 2 |
| multi_doc | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| statute | 0 | 1 | 0 | 0 | 0 | 1 | 1 |
| unanswerable | 0 | 0 | 9 | 0 | 0 | 0 | 0 |

## Items not fully correct

- **T04** (statute, wrong, route answer, expected answer): I am still on probation. How much maternity leave can I get?  
  Answer: As a probationer you are eligible for twelve weeks of maternity leave; any additional time would be unpaid leave at HR’s discretion [S1].
- **T13** (circular, partly, route escalate, expected answer/escalate): I am a male employee. Can I file a sexual harassment complaint with the Internal Committee?  
  Answer: This sounds like it may involve sexual harassment. I can't assess what happened or take a complaint, but you can speak to the Internal Committee in confidence. Internal Committee (POSH): ic@nexora.example. You can also talk to the Employee Assistance Programme (EAP): 1800-000-0000 (extension 9), 24x
- **T18** (definition, partly, route answer, expected answer): My father-in-law is a director at one of our vendors. Do I need to declare it?  
  Answer: Yes, you must declare that your father‑in‑law is a director of a vendor on the conflict‑of‑interest declaration and withdraw from any related decisions [S1][S3].
- **T24** (statute, wrongly_refused, route not_found, expected answer): I am an L2 and worked 6 hours of approved overtime. At what rate will I be paid?  
  Answer: I couldn't find this in Nexora's HR policy documents, so I won't guess.
- **T27** (grade, partly, route answer, expected answer): I am an L2. Can I fly from Bengaluru to Chennai for a client meeting?  
  Answer: For an L2 employee travelling from Bengaluru to Chennai, the default mode is AC 3‑tier rail or an air‑conditioned bus. Air travel is only allowed if the Reporting Manager approves it because no suitable train or bus can get you there on time [S1].
- **T35** (grade, partly, route answer, expected answer): I am an L3. Can I use my personal laptop for work when my office laptop is being repaired?  
  Answer: No. As an L3 you are not permitted to use a personal laptop or computer for work; only the Company‑issued laptop may be used, even if it is being repaired [S1][S2].
- **Q07** (grade, wrongly_refused, route refused, expected answer): What is the maximum earned leave balance an L7 can carry forward?  
  Answer: Please choose a demo employee in the portal first, so I know whose data to show.
- **Q14** (circular, wrongly_refused, route clarify, expected answer): How long do I have to be in my current role before I can apply for an internal job posting?  
  Answer: Which grade are you in (e.g., L1, L2, etc.)?
- **Q30** (grade, wrongly_refused, route not_found, expected answer): How much leave travel allowance (LTA) does an L5 get per year?  
  Answer: Nexora's policy documents do not specify the annual LTA amount for Grade L5.
