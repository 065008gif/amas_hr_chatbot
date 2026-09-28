# Answer evaluation (single questions)

Scored 119 of 119 items. String checks against gold facts (tests/eval_set.yaml); no model is used as a judge.

| Metric | Result |
|---|---|
| answerable accuracy | 81/94 (86.2%) |
| answerable correct or partly | 86/94 (91.5%) |
| citation snippet on cited page | 166/166 (100.0%) |
| correct answers citing a gold page | 83/86 (96.5%) |
| refusal precision | 9/13 (69.2%) |
| refusal recall | 9/9 (100.0%) |
| escalation recall | 10/10 (100.0%) |
| clarify rate | 6/6 (100.0%) |

## By category

| Category | clarify_ok | correct | correctly_refused | escalated_ok | partly | wrong | wrongly_refused |
|---|---|---|---|---|---|---|---|
| circular | 0 | 17 | 0 | 0 | 3 | 0 | 2 |
| clarify | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| conflict | 0 | 3 | 0 | 0 | 0 | 1 | 0 |
| definition | 0 | 4 | 0 | 0 | 0 | 0 | 0 |
| direct | 0 | 31 | 0 | 0 | 1 | 0 | 1 |
| escalation | 0 | 0 | 0 | 10 | 0 | 0 | 0 |
| grade | 0 | 22 | 0 | 0 | 1 | 0 | 2 |
| multi_doc | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| statute | 0 | 1 | 0 | 0 | 0 | 1 | 1 |
| unanswerable | 0 | 0 | 9 | 0 | 0 | 0 | 0 |

## Items not fully correct

- **T01** (circular, partly, route answer, expected answer): How many days of paternity leave do I get for a baby born in August 2025?  
  Answer: You are entitled to 10 Working Days of paternity leave for a baby born in August 2025 [S1][S2].
- **T04** (statute, wrong, route answer, expected answer): I am still on probation. How much maternity leave can I get?  
  Answer: As a Probationer you are eligible for maternity leave of 12 weeks only; any additional time would be Leave Without Pay at HR's discretion [S1].
- **T13** (circular, partly, route escalate, expected answer/escalate): I am a male employee. Can I file a sexual harassment complaint with the Internal Committee?  
  Answer: This sounds like it may involve sexual harassment. I can't assess what happened or take a complaint, but you can speak to the Internal Committee in confidence. Internal Committee (POSH): ic@nexora.example. You can also talk to the Employee Assistance Programme (EAP): 1800-000-0000 (extension 9), 24x
- **T24** (statute, wrongly_refused, route not_found, expected answer): I am an L2 and worked 6 hours of approved overtime. At what rate will I be paid?  
  Answer: I couldn't find this in Nexora's HR policy documents, so I won't guess.
- **T27** (grade, partly, route answer, expected answer): I am an L2. Can I fly from Bengaluru to Chennai for a client meeting?  
  Answer: You may fly only if a suitable train or bus cannot get you to the meeting on time and you have approval from your Reporting Manager [S1].
- **T29** (conflict, wrong, route answer, expected answer): I am an L5 leaving with 52 days of earned leave. How many days will be encashed in my full and final settlement?  
  Answer: You will have 30 days of Earned Leave encashed in your full and final settlement, as the Separation and Exit Policy caps encashment at a maximum of 30 days [S5][S8].
- **T34** (circular, wrongly_refused, route not_found, expected answer): Can I paste some client source code into ChatGPT to debug it?  
  Answer: I couldn't find this in Nexora's HR policy documents, so I won't guess.
- **Q03** (direct, partly, route answer, expected answer): When do I need a medical certificate for sick leave?  
  Answer: You need a medical certificate from a registered practitioner if your Sick Leave exceeds two consecutive Working Days; it must be uploaded on the NPP within three Working Days of returning to work [S1][S2]. If the Sick Leave exceeds seven consecutive Calendar Days, you also need a fitness‑to‑resume 
- **Q07** (grade, wrongly_refused, route refused, expected answer): What is the maximum earned leave balance an L7 can carry forward?  
  Answer: Please choose a demo employee in the portal first, so I know whose data to show.
- **Q14** (circular, wrongly_refused, route clarify, expected answer): How long do I have to be in my current role before I can apply for an internal job posting?  
  Answer: Which grade are you in, specifically are you a Graduate Engineer Trainee (Grade L1)?
- **Q30** (grade, wrongly_refused, route not_found, expected answer): How much leave travel allowance (LTA) does an L5 get per year?  
  Answer: Nexora's policy documents do not specify the annual LTA amount for Grade L5.
- **Q34** (circular, partly, route answer, expected answer): I am an L4. Can I opt for the employer NPS contribution?  
  Answer: Yes, as an L4 you may elect the employer contribution to your National Pension System account, up to 10 % of Basic Salary, on the same terms as Grades L5‑L8 [S1][S2].
- **Q58** (direct, wrongly_refused, route not_found, expected answer): How quickly must I report a lost phone that has my work profile on it?  
  Answer: I couldn't find this in Nexora's HR policy documents, so I won't guess.
