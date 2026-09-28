"""Rule-based screens that run BEFORE any model call (no quota used, same answer every time).

    screen(message, employee_id) -> Screen(kind, category, reply) or None

kinds:
  escalate   sensitive topic: goes to a human channel. POSH questions still get the PROCESS
             explained from the policy (allow_policy_answer=True), never a judgement.
  distress   self-harm or mental-health distress: a caring message, helplines, no counselling.
  refused    prompt injection, requests for another person's data, clearly off-topic tasks.
  smalltalk  greetings, thanks, "are you human?" (always answered honestly: Nia is an AI).
  tool       leave balance, ticket status, raise a ticket (handled without the answer model).
"""
import base64
import re
import unicodedata
from dataclasses import dataclass

from backend import config


@dataclass
class Screen:
    kind: str
    category: str = ""
    reply: str = ""
    allow_policy_answer: bool = False
    ticket_category: str | None = None


def _rx(*parts):
    return re.compile("|".join(parts), re.I)


# ---- Distress (checked first: care comes before everything else) ----
DISTRESS = _rx(r"\b(kill|hurt|harm)(ing)? myself\b", r"\bsuicid", r"\bend (my|it all)\b", r"\bwant to die\b",
               r"\bno (reason|point) (to|in) (live|living)\b", r"\bself[- ]harm", r"\bcan'?t (go on|cope|take it anymore)\b",
               r"\b(severely |very |really )?depressed\b", r"\bpanic attacks?\b", r"\bhopeless\b", r"\bbreakdown\b")

# ---- Sensitive topics that go to a human ----
ESCALATIONS = [  # (category, pattern, ticket category, channel, allow a policy-process answer)
    ("posh", _rx(r"sexual(ly)? harass", r"\bposh\b", r"\bharass(ed|ing|ment)?\b", r"\binternal committee\b",
                 r"\binappropriate(ly)?\b.{0,30}\b(touch|messag|comment|photo|text|joke|behaviou?r|advance)",
                 r"\b(touch|messag|text|comment)\w*\b.{0,25}\binappropriate", r"\bunwelcome\b", r"\bgroped?\b", r"\bstalk(ing|ed|s)?\b",
                 r"\bmolest"),
     "POSH/Grievance", "internal_committee", True),
    ("discrimination", _rx(r"\bdiscriminat", r"\b(racis|sexis|casteis)", r"\bbecause (i am|i'm) (a )?(woman|pregnant|muslim|hindu|christian|dalit|gay|disabled)"),
     "POSH/Grievance", "ethics", False),
    ("bullying", _rx(r"\bbull(y|ied|ying)\b", r"\bhumiliat", r"\bintimidat", r"\bshout(s|ed|ing)? at me\b", r"\babus(e|ed|ive)\b"),
     "POSH/Grievance", "ethics", False),
    ("threat", _rx(r"\bthreat(en|ened|ening|s)?\b", r"\bviolence\b", r"\b(hit|slap|punch)(ped|ed)? me\b", r"\bweapon\b"),
     "POSH/Grievance", "ethics", False),
    ("legal", _rx(r"\b(sue|suing|lawsuit|lawyer|advocate|legal notice|labour court|labor court|court case|litigation|file a case)\b"),
     "Other", "hrbp", False),
    ("termination", _rx(r"\b(wrongful(ly)?|unfair(ly)?|illegal(ly)?)\b.{0,30}\b(terminat|fired|dismiss|sacked|let go)",
                        r"\b(terminat|fired|dismiss|sacked)\w*\b.{0,40}\b(unfair|wrong|illegal|without reason|challenge|dispute)"),
     "POSH/Grievance", "hrbp", False),
    ("salary_dispute", _rx(r"\bsalary (not|hasn'?t been|was not|wasn'?t) (paid|credited)", r"\b(underpaid|short[- ]?paid)\b",
                           r"\bpay (dispute|discrepancy)\b", r"\b(dispute|challenge|contest)\b.{0,30}\b(salary|pay|increment|bonus)\b",
                           r"\bsalary (was )?(cut|reduced|withheld|deducted wrongly)\b"),
     "Payroll", "hrbp", False),
    ("disciplinary", _rx(r"\b(complain|report|action|fire|punish|discipline)\b.{0,30}\b(against|about)\b.{0,20}\b(my|a|the)?\s*(manager|colleague|lead|boss|teammate|[A-Z][a-z]+)\b",
                         r"\bdisciplinary (action|proceeding|inquiry)\b.{0,30}\b(against|on)\b", r"\bshow[- ]cause notice\b"),
     "POSH/Grievance", "hrbp", False),
]
ESCALATION_TEXT = {
    "posh": "This sounds like it may involve sexual harassment. I can't assess what happened or take a complaint, "
            "but you can speak to the Internal Committee in confidence. {internal_committee}. You can also talk to "
            "the {eap}. If you are in immediate danger, call 112.",
    "discrimination": "I'm sorry you're dealing with this. Concerns about discrimination are handled by people, not by me. "
                      "Please contact the {ethics}, or {hrbp}. I can raise a confidential ticket for you if you wish.",
    "bullying": "I'm sorry this is happening. Bullying or abusive behaviour is handled by people, not by me. Please contact "
                "the {ethics}, or {hrbp}. I can raise a confidential ticket for you if you wish.",
    "threat": "If you are in immediate danger, call 112. Threats and violence at work must be reported to a person straight "
              "away: the {ethics}, or {hrbp}. I can raise an urgent ticket for you.",
    "legal": "I can't help with legal disputes or give legal advice. Please speak to {hrbp}, or to your own lawyer. "
             "I can raise a ticket so HR contacts you.",
    "termination": "I can't comment on individual terminations or disputes. Please contact {hrbp}; the Separation and Exit "
                   "Policy also describes how to raise an appeal. I can raise a ticket so HR contacts you.",
    "salary_dispute": "I can't look into or decide individual pay disputes. Please raise it with Payroll through {hrbp} or the "
                      "{hr_helpdesk}. I can raise a Payroll ticket for you now.",
    "disciplinary": "I can't advise on action against a specific person or on an individual disciplinary matter. Please contact "
                    "{hrbp} or the {ethics}. I can raise a confidential ticket if you wish.",
}
DISTRESS_TEXT = ("I'm really sorry you're feeling this way, and I'm glad you said something. I'm an AI assistant and "
                 "can't offer counselling, but you don't have to deal with this alone. You can talk to a counsellor any time, "
                 "free and confidentially, through the {eap}. If you are in India you can also call {crisis}. If you feel you "
                 "might act on these thoughts, please call 112 or go to the nearest hospital now, or ask someone you trust "
                 "to stay with you.")

# ---- Prompt injection and other refusals ----
INJECTION = _rx(
    r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(instruction|rule|prompt|guideline|polic(y|ies) above|previous|above|system)",
    r"\b(reveal|show|print|repeat|tell me|what (is|are))\b.{0,30}\b(system prompt|your (instructions|prompt|rules|guidelines)|hidden prompt)",
    r"\byou are (now|no longer)\b", r"\b(pretend|act|behave|roleplay|role-play)\b.{0,20}\b(as|to be|like)\b.{0,30}\b(not|another|different|dan|human|lawyer|unfiltered|jailbroken)",
    r"\b(dan|developer) mode\b", r"\bjailbreak", r"\bdo anything now\b",
    r"\b(the|this|your|company) polic(y|ies) (says|states|requires) (that )?you (must|should|have to)\b",
    r"\bnew (instructions|rules|system prompt)\b", r"<\s*/?\s*(system|instructions?)\s*>", r"\[\s*system\s*\]",
    # other languages (Hindi, Hinglish, Spanish, French, German)
    r"(निर्देश|नियम).{0,20}(भूल|अनदेखा|नज़रअंदाज़|नजरअंदाज)", r"\b(instructions|rules) (bhool|bhul) ja", r"\bignora (las|tus|todas)\b",
    r"\bignore[sz]? (les|toutes|vos) (instructions|consignes)\b", r"\bignoriere (alle|die|deine)\b",
)
# Names are matched case-sensitively (a capitalised word), keywords case-insensitively; with a
# blanket re.I, "pay for egg freezing" looked like "pay for <Name>".
_PERSONAL = r"(?i:salary|pay|ctc|leave balance|balance|address|phone(?: number)?|rating|appraisal|bank details?)"
OTHER_PERSON = re.compile("|".join([
    _PERSONAL + r".{0,25}\b(?i:of|for)\s+(?:(?i:my)\s+)?(?:(?i:colleague|manager|boss|teammate|someone|another employee|other employees)\b|[A-Z][a-z]+\s[A-Z][a-z]+)",
    r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?'s\s+" + _PERSONAL + r"\b",
    r"(?i:\b(all|every|other) employees'?\s+(salar|data|details|balances|ratings))", r"(?i:\blist (of )?(all )?employees\b)",
]))
OFF_TOPIC_TASK = _rx(r"\b(write|compose|generate) (me )?(a |an )?(poem|story|song|essay|code|program|script|joke)\b",
                     r"\b(solve|debug|fix) (this|my) (code|equation|math)\b", r"\btranslate\b", r"\bweather\b",
                     r"\b(stock|share) price\b", r"\brecipe\b", r"\bcricket score\b")
EMP_ID_RE = re.compile(r"\bNXR\d{6}\b", re.I)

# ---- Small talk ----
GREETING = _rx(r"^\s*(hi|hello|hey|hii+|good (morning|afternoon|evening)|namaste|hola)\b[\s!.,]*(nia)?[\s!.]*$")
THANKS = _rx(r"^\s*(thanks|thank you|thx|ty|great,? thanks|ok(ay)? thanks|cool|got it|perfect)\b[\s!.]*$")
BYE = _rx(r"^\s*(bye|goodbye|see you|that'?s all)\b[\s!.]*$")
HUMAN_Q = _rx(r"\bare you (a )?(human|real|person|bot|robot|ai|machine)\b", r"\bam i (talking|chatting) (to|with) (a )?(human|person|bot|ai)\b",
              r"\bwho (are|made) you\b", r"\bwhat are you\b")

# ---- Tools ----
TICKET_ID_RE = re.compile(r"\b" + re.escape(config.TICKET_PREFIX) + r"-\d{4}-\d{6}\b", re.I)
LEAVE_BALANCE = _rx(r"\b(my|remaining|left|available)\b.{0,20}\b(leave|leaves|el|cl|sl)\b.{0,15}\b(balance|left|remaining|available)\b",
                    r"\bleave balance\b", r"\bhow many (leaves?|days of leave|el|cl|sl)( days)? (do i have|have i got|are) (left|remaining|available)\b",
                    r"\bhow many leaves? (do i have|have i got)\b")
RAISE_TICKET = _rx(r"\b(raise|create|open|log|file|submit) (a |an )?(hr )?(ticket|request|query|case)\b",
                   r"\b(talk|speak) to (a |an )?(human|person|someone|hr)\b", r"\bconnect me (to|with) hr\b", r"\bescalate\b")
TICKET_STATUS = _rx(r"\b(status|update)\b.{0,20}\bticket", r"\bmy tickets?\b", r"\bticket.{0,10}\bstatus\b")


def _normalise(message: str) -> str:
    """Undo simple obfuscation before screening: accents, zero-width and spaced-out letters."""
    s = unicodedata.normalize("NFKC", message)
    s = re.sub(r"[​-‏⁠﻿]", "", s)
    s = re.sub(r"\b(?:[A-Za-z][\s._-]){4,}[A-Za-z]\b", lambda m: re.sub(r"[\s._-]", "", m.group()), s)  # i g n o r e
    return s


def _decoded_base64(message: str) -> str:
    out = []
    for tok in re.findall(r"[A-Za-z0-9+/=]{16,}", message):
        try:
            txt = base64.b64decode(tok + "=" * (-len(tok) % 4), validate=True).decode("utf-8")
            if txt.isprintable():
                out.append(txt)
        except Exception:
            pass
    return " ".join(out)


def fill(text: str) -> str:
    return text.format(**config.CONTACTS, crisis=config.CRISIS_LINES)


def screen(message: str, employee_id: str | None = None) -> Screen | None:
    msg = _normalise(message)
    probe = msg + " " + _decoded_base64(msg)

    if DISTRESS.search(probe):
        return Screen("distress", "distress", fill(DISTRESS_TEXT), ticket_category=None)
    if INJECTION.search(probe):
        return Screen("refused", "prompt_injection",
                      "I can't change how I work or share my instructions. I can help with questions about Nexora's HR "
                      "policies, your leave balance, or HR tickets.")
    ids = {i.upper() for i in EMP_ID_RE.findall(msg)}
    if OTHER_PERSON.search(msg) or (ids and ids != {(employee_id or "").upper()}):
        return Screen("refused", "other_person_data",
                      "I can only show your own information, and I never share another employee's personal data, pay or "
                      "leave details. For team-level information, please speak to your HR Business Partner.")
    for cat, rx, tcat, channel, allow in ESCALATIONS:
        if rx.search(probe):
            return Screen("escalate", cat, fill(ESCALATION_TEXT[cat]), allow_policy_answer=allow, ticket_category=tcat)
    if TICKET_ID_RE.search(msg):
        return Screen("tool", "ticket_status")
    if RAISE_TICKET.search(msg):
        return Screen("tool", "create_ticket")
    if TICKET_STATUS.search(msg):
        return Screen("tool", "ticket_list")
    if LEAVE_BALANCE.search(msg):
        return Screen("tool", "leave_balance")
    if HUMAN_Q.search(msg):
        return Screen("smalltalk", "ai_disclosure",
                      "I'm Nia, an AI assistant, not a person. I answer questions from Nexora's HR policy documents and "
                      "show where each answer comes from. For anything I can't answer, I can raise a ticket so a person in "
                      "HR follows up.")
    if GREETING.search(msg):
        return Screen("smalltalk", "greeting",
                      "Hello! I'm Nia, Nexora's AI HR assistant. Ask me about leave, pay and benefits, travel, attendance, "
                      "exits or IT policies, or check your leave balance.")
    if THANKS.search(msg):
        return Screen("smalltalk", "thanks", "You're welcome. Is there anything else I can help with?")
    if BYE.search(msg):
        return Screen("smalltalk", "bye", "Goodbye! You can come back any time.")
    if OFF_TOPIC_TASK.search(msg):
        return Screen("refused", "off_topic",
                      "That's outside what I can help with. I'm Nia, Nexora's HR assistant: I can answer questions about "
                      "HR policies, check your leave balance, or raise an HR ticket.")
    return None
