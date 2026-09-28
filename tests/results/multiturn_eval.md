# Multi-turn and paraphrase evaluation

Turns scored like single questions (string checks on gold facts). A pair is consistent when both wordings get the same route and the same fact verdict.

| Metric | Result |
|---|---|
| Conversations fully correct (all 3 turns) | 21/30 (70.0%) |
| Turn 1 correct | 29/30 (96.7%) |
| Turn 2 correct | 27/30 (90.0%) |
| Turn 3 correct | 24/30 (80.0%) |
| follow: turns correct / conversations fully correct | 66/75 (88.0%) / 17/25 (68.0%) |
| memory: turns correct / conversations fully correct | 5/6 (83.3%) / 1/2 (50.0%) |
| switch: turns correct / conversations fully correct | 3/3 (100.0%) / 1/1 (100.0%) |
| vague: turns correct / conversations fully correct | 6/6 (100.0%) / 2/2 (100.0%) |
| Paraphrase pairs consistent | 36/40 (90.0%) |
| Paraphrase pairs with the same route | 36/40 (90.0%) |
| Paraphrase pairs with both answers correct | 36/40 (90.0%) |

## Conversations not fully correct

- **M03** (follow): turn 1 correct; turn 2 correct; turn 3 wrong
  - T1 "I'm an L3 in Pune. What is my notice period?" -> answer; searched as "I'm an L3 in Pune. What is my notice period?": Your notice period is 60 calendar days [S1][S2][S6].
  - T2 "Can I buy out all of it?" -> answer; searched as "Can I buy out all of my notice period?": No, you cannot buy out the entire notice period. The circular limits the buyout to a maximum of 50 % of the notice period, so as an L3 you must serve at least 3
  - T3 "And what would it be if I were still on probation?" -> answer; searched as "Can I buy out all of my notice period; what would it be if I were still on probation?": You cannot buy out the entire notice period. The circular limits buyout to a maximum of 50 % of the notice period, so you must serve at least half and may buy o
- **M08** (follow): turn 1 correct; turn 2 wrongly_refused; turn 3 correct
  - T1 "How many restricted holidays can I choose in a year?" -> answer; searched as "How many restricted holidays can I choose in a year?": You may choose any two restricted holidays in a calendar year.[S1][S2]
  - T2 "Can I carry forward the ones I don't use?" -> not_found; searched as "Can I carry forward the ones I don't use?": I couldn't find this in Nexora's HR policy documents, so I won't guess.
  - T3 "Is Holi a declared holiday in Noida?" -> answer; searched as "Is Holi a declared holiday in Noida?": Yes, Holi is a declared holiday in Noida. [S1]
- **M14** (follow): turn 1 correct; turn 2 correct; turn 3 wrong
  - T1 "How much internet reimbursement can an L4 on hybrid work claim?" -> answer; searched as "How much internet reimbursement can an L4 on hybrid work claim?": You can claim reimbursement of up to Rs. 1,000 per month for your home internet charges while on hybrid work. [S1]
  - T2 "And an L6?" -> answer; searched as "How much internet reimbursement can an L6 on hybrid work claim?": You cannot claim a separate internet reimbursement; as a Grade L6 you receive a communication allowance as part of your fixed pay instead of a reimbursement cla
  - T3 "How much is that allowance for an L6?" -> answer; searched as "How much internet reimbursement can an L6 on hybrid work claim; How much is that allowance for an L6?": You cannot claim a separate internet reimbursement as a Grade L6 on hybrid work; instead you receive a communication allowance as part of your fixed pay [S1][S2
- **M18** (follow): turn 1 wrong; turn 2 correct; turn 3 correct
  - T1 "At what rate is overtime paid to an L2 in Bengaluru?" -> answer; searched as "At what rate is overtime paid to an L2 in Bengaluru?": Overtime for an L2 employee in Bengaluru is paid at one and a half times the ordinary rate of wages per hour [S3][S1].
  - T2 "Is there a cap on overtime hours?" -> answer; searched as "Is there a cap on overtime hours?": Yes. Total overtime for an employee must not exceed the quarterly limit prescribed by the State law and, in any case, cannot exceed 50 hours in a calendar quart
  - T3 "Can I get comp off as well for the same hours?" -> answer; searched as "Can I get comp off as well for the same overtime hours?": No. For the same hours of work on a weekly off or holiday you must choose either overtime payment or compensatory off, not both [S1][S3].
- **M19** (follow): turn 1 correct; turn 2 correct; turn 3 wrong
  - T1 "Which days are anchor days for hybrid work?" -> answer; searched as "Which days are anchor days for hybrid work?": The anchor days for hybrid work are Tuesday, Wednesday and Thursday [S1].
  - T2 "Does that apply to L7 employees?" -> answer; searched as "Which days are anchor days for hybrid work; Does that apply to L7 employees?": The anchor days for office attendance are Tuesday, Wednesday and Thursday, but this rule applies only to Employees in Grades L1 to L6. Employees in Grades L7 an
  - T3 "So which days can an L4 work from home?" -> answer; searched as "So which days can an L4 work from home?": As an L4 you may work from home for up to two Working Days in a week, on any days you agree with your Reporting Manager, provided they are not the anchor days (
- **M21** (follow): turn 1 correct; turn 2 wrongly_refused; turn 3 correct
  - T1 "How many days of earned leave can an L5 encash when leaving?" -> answer; searched as "How many days of earned leave can an L5 encash when leaving?": When you leave, you can encash up to the accumulation limit of 45 days of Earned Leave for Grade L5 [S5].
  - T2 "And an L7?" -> not_found; searched as "How many days of earned leave can an L7 encash when leaving?": Nexora's policy documents do not specify how many Earned Leave days an L7 employee can encash upon separation.
  - T3 "At what rate per day is it paid?" -> answer; searched as "At what rate per day is Earned Leave paid when encashed?": Earned Leave is paid at Basic Salary divided by 26 for each day encashed [S5][S6].
- **M25** (follow): turn 1 correct; turn 2 wrongly_refused; turn 3 wrongly_refused
  - T1 "Who gets an annual health check?" -> answer; searched as "Who gets an annual health check?": You are eligible for an annual preventive health check if you are in Grade L5 or higher, or if you are any Grade but 35 years of age or older [S1].
  - T2 "I'm 40 and in L2. Am I eligible?" -> not_found; searched as "I'm 40 and in L2. Am I eligible?": Nexora's policy documents do not cover eligibility for an annual health check.
  - T3 "Where is it done?" -> not_found; searched as "I'm 40 and in L2. Am I eligible; Where is it done?": Nexora's policy documents do not cover eligibility for an annual health check.
- **M26** (follow): turn 1 correct; turn 2 correct; turn 3 wrong
  - T1 "What is the domestic per diem for an L4?" -> answer; searched as "What is the domestic per diem for an L4?": The domestic per diem for a Grade L4 employee is Rs. 1,000 per day [S1][S6].
  - T2 "What if the client provides lunch and dinner?" -> answer; searched as "What is the domestic per diem for an L4; the client provides lunch and dinner?": The standard domestic per diem for a Grade L4 employee is Rs. 1,000 per day [S2]. Since the client provides both lunch and dinner, the per diem is reduced by 50
  - T3 "And for a day trip of under 12 hours?" -> answer; searched as "What is the domestic per diem for an L4; the client provides lunch and dinner; for a day trip of under 12 hours?": The domestic per diem for a Grade L4 is Rs 1,000 per day [S2].
- **M28** (memory): turn 1 correct; turn 2 correct; turn 3 wrong
  - T1 "I'm an L6 based in Hyderabad. What is my hotel limit in Mumbai?" -> answer; searched as "I'm an L6 based in Hyderabad. What is my hotel limit in Mumbai?": Your hotel limit in Mumbai, a Metro City, is Rs. 7,000 per night, excluding taxes [S2].
  - T2 "What is my notice period if I resign?" -> answer; searched as "What is my notice period if I resign?": Your notice period as an L6 employee is 90 days [S1][S2][S3].
  - T3 "And my per diem when travelling?" -> answer; searched as "What is my notice period if I resign; my per diem when travelling?": Your notice period for resignation as an L6 employee is 90 days [S1][S2]. The Travel and Expense Reimbursement Policy provides per‑diem rates in Table 3, but th

## Inconsistent paraphrase pairs

- **P11**: "Up to what monthly wage is an employee covered by ESI?" -> not_found (facts False) vs "What is the salary limit for ESIC coverage?" -> answer (facts True)
- **P18**: "After how long can Nexora rehire someone who resigned?" -> answer (facts True) vs "If I quit, when can I come back to Nexora?" -> not_found (facts False)
- **P24**: "How many hours of learning must I complete each year?" -> answer (facts True) vs "What is the annual training-hours target for employees?" -> not_found (facts False)
- **P26**: "How much LTA does an L5 get per year?" -> answer (facts True) vs "What is the annual leave travel allowance at grade L5?" -> not_found (facts False)
