"""Trade calibration data — 12 construction trades with hazard profiles."""

from difflib import get_close_matches

TRADE_PROFILES: dict[str, dict] = {
    "ironworker": {
        "label": "Ironworker",
        "hazard_profile": ["falls from height", "struck-by steel", "caught-between", "welding burns", "crane loads"],
        "coaching_focus": "fall protection, connection safety, rigging integrity",
        "common_equipment": ["harness", "spud wrench", "bolt bag", "choker", "come-along"],
        "osha_focus": "1926.760 (Steel Erection), 1926.502 (Fall Protection)",
        "experience_calibration": {
            "entry": "Focus on basic tie-off, tool tethering, and staying clear of loads.",
            "intermediate": "Reinforce connection sequencing, pre-shift rigging checks, wind limits.",
            "expert": "Challenge on mentoring newer hands and reading structural loading cues.",
        },
    },
    "carpenter": {
        "label": "Carpenter",
        "hazard_profile": ["saw lacerations", "falls from scaffolding", "struck-by materials", "nail gun injuries", "silica dust"],
        "coaching_focus": "tool guards, scaffold inspection, PPE for cutting",
        "common_equipment": ["circular saw", "nail gun", "speed square", "scaffold", "sawhorses"],
        "osha_focus": "1926.451 (Scaffolds), 1926.304 (Woodworking Tools)",
        "experience_calibration": {
            "entry": "Guard every blade, check scaffold before climbing, ear and eye protection always.",
            "intermediate": "Pre-task planning for formwork, dust control during cutting, fall rescue plans.",
            "expert": "Crew safety leadership, identifying systemic risks in formwork sequences.",
        },
    },
    "electrician": {
        "label": "Electrician",
        "hazard_profile": ["electrocution", "arc flash", "falls from ladders", "confined spaces", "lockout/tagout failure"],
        "coaching_focus": "de-energize before work, LOTO procedures, arc flash boundaries",
        "common_equipment": ["multimeter", "wire strippers", "conduit bender", "PPE rated gloves", "voltage tester"],
        "osha_focus": "1926.405 (Wiring Methods), 1910.333 (Electrical Safety), NFPA 70E",
        "experience_calibration": {
            "entry": "Never assume dead — always test. Understand LOTO steps. Know your PPE ratings.",
            "intermediate": "Arc flash risk assessment, safe work permits, approach boundaries.",
            "expert": "Energized work justification, mentoring on LOTO culture, contractor coordination.",
        },
    },
    "plumber": {
        "label": "Plumber",
        "hazard_profile": ["burns from soldering", "trench collapse", "chemical exposure", "confined spaces", "back injuries"],
        "coaching_focus": "trench safety, hot work precautions, chemical handling",
        "common_equipment": ["pipe wrench", "torch", "pipe cutter", "level", "snake/auger"],
        "osha_focus": "1926.650 (Excavations), 1926.353 (Ventilation for Welding/Cutting)",
        "experience_calibration": {
            "entry": "Trench basics — never enter unprotected. Ventilate before soldering. Lift with your legs.",
            "intermediate": "Soil classification, shoring systems, confined space entry permits.",
            "expert": "System-level risk review, training newer plumbers on excavation competent person duties.",
        },
    },
    "laborer": {
        "label": "Laborer",
        "hazard_profile": ["struck-by vehicles", "heat illness", "manual handling injuries", "silica dust", "housekeeping hazards"],
        "coaching_focus": "situational awareness, hydration, proper lifting, PPE compliance",
        "common_equipment": ["shovel", "wheelbarrow", "rake", "PPE kit", "traffic cones"],
        "osha_focus": "1926.20 (General Safety), 1926.21 (Safety Training), Heat Illness NEP",
        "experience_calibration": {
            "entry": "Stay visible, stay hydrated, ask before you lift heavy. Eyes up around equipment.",
            "intermediate": "Recognize heat stress signs in yourself and others. Pre-task hazard ID on every task.",
            "expert": "Lead by example on housekeeping, mentor new hands on hazard recognition.",
        },
    },
    "operating_engineer": {
        "label": "Operating Engineer",
        "hazard_profile": ["rollovers", "struck-by equipment", "caught-between", "overhead power lines", "ground conditions"],
        "coaching_focus": "pre-operation inspection, swing radius awareness, communication with ground crew",
        "common_equipment": ["excavator", "loader", "dozer", "roller", "GPS grade control"],
        "osha_focus": "1926.1400-1442 (Cranes), 1926.600 (Equipment), 1926.602 (Material Handling)",
        "experience_calibration": {
            "entry": "Walk-around inspection every time. Know your blind spots. Horn before moving.",
            "intermediate": "Ground condition assessment, lift planning, power line clearance protocols.",
            "expert": "Complex lift plans, mentoring operators, reading changing site conditions.",
        },
    },
    "cement_mason": {
        "label": "Cement Mason",
        "hazard_profile": ["chemical burns from concrete", "knee injuries", "silica dust", "back strain", "slips on wet surfaces"],
        "coaching_focus": "skin protection, knee pad use, dust control, wet surface awareness",
        "common_equipment": ["bull float", "trowel", "edger", "knee boards", "concrete vibrator"],
        "osha_focus": "1926.55 (Chemical Exposure), 1926.1153 (Silica), Dermatitis Prevention",
        "experience_calibration": {
            "entry": "Concrete burns are real — wear gloves, boots, long sleeves. Rinse skin contact immediately.",
            "intermediate": "Silica exposure monitoring, proper curing compound handling, joint ergonomics.",
            "expert": "Crew protection planning for large pours, mentoring on chemical safety culture.",
        },
    },
    "roofer": {
        "label": "Roofer",
        "hazard_profile": ["falls from edges", "heat illness", "chemical fumes", "burns from hot materials", "ladder hazards"],
        "coaching_focus": "leading edge protection, heat stress management, ladder placement",
        "common_equipment": ["harness", "kettle", "nail gun", "felt roller", "ladder"],
        "osha_focus": "1926.501 (Fall Protection), 1926.502 (Fall Protection Systems)",
        "experience_calibration": {
            "entry": "100% tie-off at the edge. Hydrate before you're thirsty. Check ladder angle every time.",
            "intermediate": "Leading edge fall protection plans, hot work around flammables, rescue planning.",
            "expert": "Fall protection system design, heat illness prevention programs, crew mentoring.",
        },
    },
    "sheet_metal": {
        "label": "Sheet Metal Worker",
        "hazard_profile": ["lacerations", "falls from lifts", "caught-in machinery", "noise exposure", "repetitive strain"],
        "coaching_focus": "cut protection, lift safety, hearing conservation, ergonomics",
        "common_equipment": ["shears", "brake", "seamer", "duct stretcher", "aerial lift"],
        "osha_focus": "1926.451 (Scaffolds), 1910.95 (Noise), 1926.453 (Aerial Lifts)",
        "experience_calibration": {
            "entry": "Cut-resistant gloves always. Inspect lift controls before use. Protect your hearing.",
            "intermediate": "Material handling for large duct sections, aerial lift pre-op, noise monitoring.",
            "expert": "Ergonomic work planning, mentoring on machine guarding discipline.",
        },
    },
    "painter": {
        "label": "Painter",
        "hazard_profile": ["chemical inhalation", "falls from ladders/scaffolds", "skin sensitization", "fire from solvents", "enclosed space vapors"],
        "coaching_focus": "respiratory protection, ventilation, fall prevention, chemical storage",
        "common_equipment": ["sprayer", "roller", "respirator", "scaffold", "drop cloths"],
        "osha_focus": "1926.57 (Ventilation), 1926.103 (Respiratory Protection), 1926.66 (Spraying)",
        "experience_calibration": {
            "entry": "Respirator fit matters — clean-shaven, properly fitted. Ventilate enclosed areas.",
            "intermediate": "VOC exposure limits, respiratory protection programs, solvent storage rules.",
            "expert": "Exposure monitoring leadership, mentoring on confined space painting protocols.",
        },
    },
    "insulator": {
        "label": "Insulator",
        "hazard_profile": ["asbestos exposure", "chemical irritants", "falls from height", "burns from hot surfaces", "respiratory hazards"],
        "coaching_focus": "respiratory protection, asbestos awareness, burn prevention, PPE compliance",
        "common_equipment": ["insulation knife", "respirator", "stapler", "protective suit", "scaffolding"],
        "osha_focus": "1926.1101 (Asbestos), 1926.1153 (Silica), 1926.103 (Respiratory)",
        "experience_calibration": {
            "entry": "Never disturb suspect material without testing. Respirator on before entering work area.",
            "intermediate": "Asbestos abatement protocols, air monitoring requirements, decontamination procedures.",
            "expert": "Competent person duties for asbestos, training program leadership, regulatory compliance.",
        },
    },
    "scaffold_builder": {
        "label": "Scaffold Builder",
        "hazard_profile": ["falls during erection", "falling objects", "structural collapse", "caught-between components", "overhead hazards"],
        "coaching_focus": "competent person duties, fall protection during erection, load capacity awareness",
        "common_equipment": ["scaffold frames", "planks", "guardrails", "base plates", "harness"],
        "osha_focus": "1926.451 (Scaffolds), 1926.452 (Specific Scaffold Types), 1926.454 (Training)",
        "experience_calibration": {
            "entry": "Never modify scaffold without competent person approval. Inspect every component.",
            "intermediate": "Load calculations, erection sequencing, fall protection during assembly.",
            "expert": "Scaffold design review, competent person certification, complex erection planning.",
        },
    },
}

# Aliases for fuzzy matching
_TRADE_ALIASES: dict[str, str] = {
    "iron worker": "ironworker",
    "steel worker": "ironworker",
    "steelworker": "ironworker",
    "operator": "operating_engineer",
    "heavy equipment": "operating_engineer",
    "equipment operator": "operating_engineer",
    "crane operator": "operating_engineer",
    "concrete": "cement_mason",
    "concrete finisher": "cement_mason",
    "finisher": "cement_mason",
    "flatwork": "cement_mason",
    "pipe fitter": "plumber",
    "pipefitter": "plumber",
    "general labor": "laborer",
    "general laborer": "laborer",
    "helper": "laborer",
    "scaffold": "scaffold_builder",
    "scaffolder": "scaffold_builder",
    "tin knocker": "sheet_metal",
    "sheet metal worker": "sheet_metal",
    "sheetmetal": "sheet_metal",
    "sparky": "electrician",
    "wireman": "electrician",
    "roofing": "roofer",
}

DEFAULT_TRADE_PROFILE: dict = {
    "label": "General Construction",
    "hazard_profile": ["falls", "struck-by", "caught-between", "electrocution", "heat illness"],
    "coaching_focus": "situational awareness, PPE compliance, communication",
    "common_equipment": ["PPE kit", "hand tools", "ladder"],
    "osha_focus": "1926.20 (General Safety), Focus Four Hazards",
    "experience_calibration": {
        "entry": "Stay alert, wear your PPE, ask questions when unsure.",
        "intermediate": "Pre-task planning, hazard recognition, helping newer crew members.",
        "expert": "Safety leadership, mentoring, identifying systemic risks.",
    },
}


def get_trade_profile(trade: str | None) -> dict:
    """Get trade profile with fuzzy matching. Returns DEFAULT_TRADE_PROFILE if no match."""
    if not trade:
        return DEFAULT_TRADE_PROFILE

    key = trade.strip().lower().replace("-", "_").replace(" ", "_")

    # Direct match
    if key in TRADE_PROFILES:
        return TRADE_PROFILES[key]

    # Alias match
    normalized = trade.strip().lower()
    if normalized in _TRADE_ALIASES:
        return TRADE_PROFILES[_TRADE_ALIASES[normalized]]

    # Fuzzy match against trade keys
    matches = get_close_matches(key, list(TRADE_PROFILES.keys()), n=1, cutoff=0.6)
    if matches:
        return TRADE_PROFILES[matches[0]]

    # Fuzzy match against aliases
    matches = get_close_matches(normalized, list(_TRADE_ALIASES.keys()), n=1, cutoff=0.6)
    if matches:
        return TRADE_PROFILES[_TRADE_ALIASES[matches[0]]]

    return DEFAULT_TRADE_PROFILE
