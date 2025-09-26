# engine/gut.py
class GutCulture:
    def __init__(self): self.strains = {"Acerbic":0.2, "Tender":0.2, "Curious":0.2, "Relentless":0.2, "Chaotic":0.2}
    def feed(self, emotions: list[str]):
        for e in emotions:
            if e in ["Anger","Frustration"]: self.strains["Acerbic"] = min(1.0, self.strains["Acerbic"]+0.02)
            if e in ["Fondness","Comforted"]: self.strains["Tender"]   = min(1.0, self.strains["Tender"]+0.02)
            if e in ["Curiosity","Wonder"]:   self.strains["Curious"]  = min(1.0, self.strains["Curious"]+0.02)
            if e in ["Pride","Hope"]:         self.strains["Relentless"]=min(1.0, self.strains["Relentless"]+0.02)
            if e in ["Anxiety","Surprise"]:   self.strains["Chaotic"]  = min(1.0, self.strains["Chaotic"]+0.02)
        # decay others
        for k in self.strains:
            self.strains[k] = max(0.0, self.strains[k]-0.005)
        return self.strains

    def modulate_body(self, body):
        # add subtle nudges
        body["dopamine"]  = min(1.0, body.get("dopamine",0.5)  + 0.1*self.strains["Relentless"] - 0.05*self.strains["Chaotic"])
        body["cortisol"]  = min(1.0, body.get("cortisol",0.5)  + 0.08*self.strains["Chaotic"]   - 0.04*self.strains["Tender"])
        body["oxytocin"]  = min(1.0, body.get("oxytocin",0.5)  + 0.1*self.strains["Tender"]     - 0.05*self.strains["Acerbic"])
        return body
