# engine/chakra_engine.py
from typing import Dict, Tuple

CHAKRAS = ["RED","ORANGE","YELLOW","GREEN","BLUE","INDIGO","VIOLET"]

class ChakraEngine:
    def __init__(self, weights: Dict[str, dict]):
        self.w = weights
        self.state = {k: {"activation": 0.5, "balance": 0.5} for k in CHAKRAS}

    def _feat(self, cocktail: Dict, body: Dict, cfg: dict) -> float:
        def emo_int(e): return (cocktail.get(e) or {}).get("intensity", 0.0)
        pos = sum(emo_int(e)*w for e,w in (cfg.get("emotions_pos") or {}).items())
        neg = sum(emo_int(e)*w for e,w in (cfg.get("emotions_neg") or {}).items())
        pos += sum((body.get(b,0.5)-0.5)*w for b,w in (cfg.get("body_pos") or {}).items())
        neg += sum((body.get(b,0.5)-0.5)*w for b,w in (cfg.get("body_neg") or {}).items())
        act = 0.5 + pos - neg
        return max(0.0, min(1.0, act))

    def step(self, cocktail: Dict, body: Dict) -> Tuple[Dict, Dict]:
        centers = {}
        body_adj = dict(body)
        for name, cfg in self.w.items():
            act = self._feat(cocktail, body, cfg)
            sp  = cfg.get("setpoint", 0.5)
            bal = 1 - abs(act - sp)
            centers[name] = {"activation": act, "balance": bal}

        if centers.get("RED",{}).get("balance",0.5) < 0.4:
            for k in ["YELLOW","BLUE","INDIGO"]:
                if k in centers: centers[k]["activation"] *= 0.95
        if centers.get("GREEN",{}).get("balance",0.5) < 0.4 and "BLUE" in centers:
            centers["BLUE"]["activation"] *= 0.95
        if centers.get("VIOLET",{}).get("balance",0.5) > 0.6:
            for k in centers:
                a = centers[k]["activation"]
                centers[k]["activation"] = a*0.98 + 0.01*0.5

        red_bal    = centers.get("RED",{}).get("balance",0.5)
        green_bal  = centers.get("GREEN",{}).get("balance",0.5)
        yellow_act = centers.get("YELLOW",{}).get("activation",0.5)
        violet_bal = centers.get("VIOLET",{}).get("balance",0.5)

        body_adj["cortisol"] = max(0, min(1, body_adj.get("cortisol",0.5) + (0.5-red_bal)*0.05 + (0.5-violet_bal)*0.04))
        body_adj["oxytocin"] = max(0, min(1, body_adj.get("oxytocin",0.5) + (green_bal-0.5)*0.06))
        body_adj["dopamine"] = max(0, min(1, body_adj.get("dopamine",0.5) + (yellow_act-0.5)*0.05))

        self.state = centers
        return centers, body_adj
