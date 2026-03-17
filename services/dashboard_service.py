from datetime import datetime, timedelta
from typing import List, Dict

TRAINING_TEMPLATES = {
    "basketball": [
        {"focus": "Shooting mechanics", "drills": ["Form shooting", "Catch-and-shoot", "Pull-up jumpers"]},
        {"focus": "Footwork & agility", "drills": ["Ladder drills", "Defensive slides", "Euro step"]},
        {"focus": "Conditioning", "drills": ["Suicide sprints", "Full-court layups", "3-on-2 transition"]},
    ],
    "golf": [
        {"focus": "Swing mechanics", "drills": ["Slow-motion swings", "Impact bag work", "Alignment drills"]},
        {"focus": "Short game", "drills": ["Chipping", "Putting distance control", "Bunker shots"]},
        {"focus": "Course management", "drills": ["Target practice", "9-hole focus round"]},
    ],
    "tennis": [
        {"focus": "Serve mechanics", "drills": ["Ball toss practice", "Serve motion shadow swings", "Kick serve practice"]},
        {"focus": "Groundstrokes", "drills": ["Forehand cross court", "Backhand down the line", "Rally consistency"]},
        {"focus": "Footwork & positioning", "drills": ["Split step timing", "Cone agility drills", "Approach shot practice"]},
    ],
    "baseball": [
        {"focus": "Throwing mechanics", "drills": ["Long toss", "Wrist snaps", "Crow hops"]},
        {"focus": "Hitting", "drills": ["Tee work", "Soft toss", "Live BP"]},
        {"focus": "Fielding", "drills": ["Ground balls", "Fly balls", "Double play footwork"]},
    ],
    "general": [
        {"focus": "Lower body explosiveness", "drills": ["Jump squats", "Lateral bounds", "Sprint intervals"]},
        {"focus": "Mobility + recovery", "drills": ["Hip openers", "Foam roll", "Light jog"]},
        {"focus": "Skill refinement", "drills": ["Footwork drills", "Reaction drills", "Core stability"]},
    ],
}


def generate_training_plan(sport: str = "general", days: int = 7) -> List[Dict]:
    today = datetime.utcnow().date()
    template = TRAINING_TEMPLATES.get(sport.lower(), TRAINING_TEMPLATES["general"])
    plan = []
    for i in range(days):
        day = today + timedelta(days=i)
        block = template[i % len(template)]
        plan.append({
            "date": str(day),
            "day_label": day.strftime("%A"),
            "focus": block["focus"],
            "drills": block["drills"],
        })
    return plan