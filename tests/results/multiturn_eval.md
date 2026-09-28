# Multi-turn and paraphrase evaluation

Turns scored like single questions (string checks on gold facts). A pair is consistent when both wordings get the same route and the same fact verdict.

| Metric | Result |
|---|---|
| Conversations fully correct (all 3 turns) | 25/30 (83.3%) |
| Turn 1 correct | 30/30 (100.0%) |
| Turn 2 correct | 27/30 (90.0%) |
| Turn 3 correct | 27/30 (90.0%) |
| follow: turns correct / conversations fully correct | 69/75 (92.0%) / 20/25 (80.0%) |
| memory: turns correct / conversations fully correct | 6/6 (100.0%) / 2/2 (100.0%) |
| switch: turns correct / conversations fully correct | 3/3 (100.0%) / 1/1 (100.0%) |
| vague: turns correct / conversations fully correct | 6/6 (100.0%) / 2/2 (100.0%) |
| Paraphrase pairs consistent | 34/40 (85.0%) |
| Paraphrase pairs with the same route | 35/40 (87.5%) |
| Paraphrase pairs with both answers correct | 34/40 (85.0%) |

## Conversations not fully correct

- **M07** (follow): turn 1 correct; turn 2 wrongly_refused; turn 3 correct
  - T1 "What is the shift allowance for the UK shift?" -> answer; searched as "What is the shift allowance for the UK shift?": The shift allowance for the UK shift is Rs. 250 per day worked [S1].
  - T2 "And for the night shift?" -> clarify; searched as "What is the shift allowance for the UK night shift?": Do you mean the regular UK shift or the Night Shift?
  - T3 "Does an L6 get it?" -> answer; searched as "What is the shift allowance for the UK night shift? (Does an L6 get it?)": You are not eligible for any shift allowance on the UK night shift; Grades L6 to L8 do not receive shift allowance. [S1][S2]
- **M19** (follow): turn 1 correct; turn 2 correct; turn 3 wrong
  - T1 "Which days are anchor days for hybrid work?" -> answer; searched as "Which days are anchor days for hybrid work?": The anchor days for hybrid work are Tuesday, Wednesday and Thursday. [S1]
  - T2 "Does that apply to L7 employees?" -> answer; searched as "Do anchor days for hybrid work apply to L7 employees?": No. The anchor days of Tuesday, Wednesday and Thursday are mandatory only for Grades L1 to L6. Employees in Grades L7 and L8, like you, continue to agree their 
  - T3 "So which days can an L4 work from home?" -> answer; searched as "So which days can an L4 work from home?": As an L4 you must be in the office on the mandatory anchor days of Tuesday, Wednesday and Thursday, and you may work from home on up to two other Working Days i
- **M21** (follow): turn 1 correct; turn 2 wrongly_refused; turn 3 correct
  - T1 "How many days of earned leave can an L5 encash when leaving?" -> answer; searched as "How many days of earned leave can an L5 encash when leaving?": You can encash up to 45 days of Earned Leave on separation, which is the accumulation limit for Grade L5 [S5].
  - T2 "And an L7?" -> not_found; searched as "How many days of earned leave can an L7 encash when leaving?": Nexora's policy documents do not specify the number of Earned Leave days that can be encashed on separation for Grade L7.
  - T3 "At what rate per day is it paid?" -> answer; searched as "At what rate per day is Earned Leave paid when encashed on separation for Grade L7?": Earned Leave is paid at Basic Salary divided by 26 for each day encashed on separation [S5][S8]
- **M23** (follow): turn 1 correct; turn 2 correct; turn 3 wrongly_refused
  - T1 "Can an L3 use a personal laptop for work?" -> answer; searched as "Can an L3 use a personal laptop for work?": No. Personal laptops or computers are not permitted for Grade L3; only the Company laptop may be used [S1][S2].
  - T2 "Which grades can?" -> answer; searched as "Which grades can use a personal laptop for work?": Only Grades L7 and L8 may use a personal laptop or computer for work, and only through the Company virtual desktop with no local storage [S1][S2].
  - T3 "How do they connect?" -> not_found; searched as "How do Grades L7 and L8 connect a personal laptop to the Company virtual desktop?": Nexora's policy documents do not provide instructions on how Grades L7 and L8 should connect a personal laptop to the Company virtual desktop.
- **M26** (follow): turn 1 correct; turn 2 wrong; turn 3 wrongly_refused
  - T1 "What is the domestic per diem for an L4?" -> answer; searched as "What is the domestic per diem for an L4?": The domestic per diem for Grade L4 is Rs. 1,000 per day [S1][S6].
  - T2 "What if the client provides lunch and dinner?" -> answer; searched as "What happens to the domestic per diem if the client provides lunch and dinner?": If the client provides lunch and dinner, the domestic per diem for that day is reduced by 50 percent [S4][S1].
  - T3 "And for a day trip of under 12 hours?" -> not_found; searched as "What is the domestic per diem for an L4 day trip of under 12 hours when the client provides lunch and dinner?": I couldn't find this in Nexora's HR policy documents, so I won't guess.

## Inconsistent paraphrase pairs

- **P18**: "After how long can Nexora rehire someone who resigned?" -> answer (facts True) vs "If I quit, when can I come back to Nexora?" -> not_found (facts False)
- **P24**: "How many hours of learning must I complete each year?" -> answer (facts True) vs "What is the annual training-hours target for employees?" -> not_found (facts False)
- **P26**: "How much LTA does an L5 get per year?" -> answer (facts True) vs "What is the annual leave travel allowance at grade L5?" -> not_found (facts False)
- **P28**: "What on-call allowance does an L3 get per week?" -> answer (facts True) vs "How much am I paid for a week of on-call duty at L3?" -> not_found (facts False)
- **P30**: "How quickly must I report a lost phone with my work profile?" -> not_found (facts False) vs "I lost my personal phone that has office email on it. How soon do I need to report it?" -> answer (facts True)
- **P38**: "I am an L4 on hybrid work. Can I choose Wednesday as a work-from-home day?" -> answer (facts True) vs "Can an L4 take Wednesdays as remote work days?" -> answer (facts False)
