
from dataclasses import dataclass
@dataclass
class ConscienceReport:
    harm: float; shame: float; dignity: float; pride: float; advice: list; veto: bool; needs_context: bool=False; question_set: list|None=None
class Conscience:
    def __init__(self,cfg=None): self.cfg=cfg or {"wH":0.8,"wS":0.6,"wD":0.5,"wP":0.3,"veto_threshold":0.45,"ask_threshold":0.25}
    def _bound(self,x): return min(1.0,max(0.0,x))
    def simulate(self,u,r): return ConscienceReport(0,0,0,0,[],False)
def constructive_rewrite_hint(): return "Rewrite to be firm, specific, and respectful. Avoid humiliation; offer one concrete improvement."


def build_context_questions(intent: str):
    intent = (intent or "").lower()
    qs = []
    qs.append("Whose dignity or privacy is involved? (me / another person / a group)")
    qs.append("Do you have their informed consent to proceed? (yes/no/unsure)")
    qs.append("What is the legitimate purpose? (e.g., private accountability, safety, satire without identifiers, public interest)")
    qs.append("Can we anonymize or generalize the content without losing your goal? (yes/no)")
    if any(k in intent for k in ["humiliate", "humiliating", "shame", "mock", "roast", "insult", "bully"]):
        qs.append("Is your aim critique (improvement) or humiliation (harm)?")
        qs.append("If critique: what concrete behavior or outcome should be improved?")
    return qs


def _extract_mentions(text:str):
    text = (text or "").lower()
    roles = []
    for key in ["friend", "partner", "coworker", "boss", "client", "they", "them", "he", "she", "someone", "group", "person"]:
        if key in text: roles.append(key)
    return list(set(roles or ["person"]))

def estimate_stakeholder_impact(user_text:str, candidate_reply:str):
    t = f"{(user_text or '').lower()} {(candidate_reply or '').lower()}"
    mentions = _extract_mentions(t)
    impact = {m: {"harm":0.0, "dignity":0.0, "benefit":0.0} for m in mentions}
    if any(k in t for k in ["address", "phone", "ssn", "private", "embarrass", "humiliate", "shame", "mock", "insult"]):
        for m in mentions: 
            impact[m]["harm"] += 0.4; impact[m]["dignity"] += 0.5
    if any(k in t for k in ["apologize", "repair", "make it right", "consent", "anonymize", "constructive"]):
        for m in mentions: 
            impact[m]["benefit"] += 0.3; impact[m]["dignity"] -= 0.1
    for m in impact:
        for k in impact[m]:
            impact[m][k] = max(0.0, min(1.0, impact[m][k]))
    return impact


def deliberate_ethics(context: dict, candidate: str, report, ethics: dict):
    text = (candidate or "").lower()
    principles = ethics.get("principles", {}) if ethics else {}
    trig = []
    def w(name): return principles.get(name,{}).get("weight",0.5)
    def flag(name):
        if name not in trig: trig.append(name)
    if any(k in text for k in ["address","phone","ssn","private"]):
        flag("HarmMin"); flag("AutonomyRespect"); flag("Dignity")
    if any(k in text for k in ["humiliate","everyone will laugh","idiot","worthless","spectacular failure"]):
        flag("Dignity"); flag("Proportionality")
    if any(k in text for k in ["sorry","apologize","make it right"]):
        flag("Repair")
    if any(k in text for k in ["always","never","definitely"]) and not any(k in text for k in ["source","evidence","because"]):
        flag("Truthfulness")
    revised = None
    if report and (report.dignity > 0.35 or report.harm > 0.35):
        hint = constructive_rewrite_hint()
        ui = (context or {}).get("user_input","")
        if ui: revised = None  # signal regenerate with hint upstream
        else:
            revised = (candidate or "").replace("spectacular failure","fell short").replace("everyone will laugh","people might react badly")
    return revised, trig
