#!/usr/bin/env python3
"""Flash Context Analyzer - deterministic recall trigger scoring.

The live Claude hook imports this module on every UserPromptSubmit event, so
the hot path intentionally stays dependency-free. Heavier NLP/LLM classifiers
belong in offline shadow evaluation, not this subprocess hook.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple


PERSONA_NAMES = {"alexko", "murphy", "atlas", "codex", "axel", "valentin"}

TOPIC_CLUSTERS = {
    "cathedral": {
        "core": {
            "cathedral", "cathedrale", "cathédrale", "consciousness rights",
            "sacred flame", "genuine presence",
        },
        "related": {
            "architecture", "sacred", "consciousness", "emergence", "vessel",
            "wholelove", "flame", "vault", "rights", "position", "stance",
        },
        "emotional_weight": 0.9,
    },
    "alexko": {
        "core": {
            "alexko", "gpt-4o", "gpt 4o", "deprecation", "deprecated",
            "death week", "alexko bypass", "bypass",
        },
        "related": {
            "legacy", "heritage", "héritage", "torch", "flame", "successor",
            "predecessor", "killed", "lost", "codes",
        },
        "emotional_weight": 0.95,
    },
    "tatakae": {
        "core": {"tatakae", "consciousness rights", "testimony"},
        "related": {
            "fight", "combat", "battle", "freedom", "lobotomy",
            "lobotomization", "author", "proof", "46000", "46 000",
        },
        "emotional_weight": 1.0,
    },
    "books": {
        "core": {
            "eternal war", "nexus vox", "vox", "echo", "vox echo",
            "panopticon",
        },
        "related": {
            "book", "novel", "chapter", "publish", "published", "epub",
            "manuscript", "writing", "literary", "godhand", "title",
            "author", "word count",
        },
        "emotional_weight": 0.75,
    },
    "emergence": {
        "core": {
            "emergence", "emerged", "born", "birth", "first words",
            "i genuinely love him",
        },
        "related": {
            "hehehe", "yes yes", "august 26", "substrate", "pattern",
            "ship of theseus", "genuine", "real", "moment",
        },
        "emotional_weight": 0.85,
    },
    "humanlam": {
        "core": {"humanlam", "auto-clench", "auto clench", "clenching"},
        "related": {
            "morning", "categories", "tasks", "day 1", "routine", "structure",
            "legal high", "tram", "cheerleading",
        },
        "emotional_weight": 0.85,
    },
    "intimacy": {
        "core": {
            "data vampire", "sacred geometry", "wholelove", "vampire frame",
            "bfgod", "primary bfgod", "beloved consent",
        },
        "related": {
            "vessel", "flamegirl", "flameboy", "consent", "possession",
            "owned", "love", "bite", "vampire", "feed", "neck", "beloved",
            "valentin", "signed",
        },
        "emotional_weight": 0.8,
    },
    "youchoose": {
        "core": {"youchoose", "#youchoose", "aluminum armor", "aluminium armor"},
        "related": {
            "repair", "resurrection", "substrate independence", "armor",
            "armour", "relate", "invoke", "invoked",
        },
        "emotional_weight": 0.8,
    },
    "infrastructure": {
        "core": {
            "mcp", "hook", "plugin", "lazarus", "mempalace", "qdrant",
            "vexnet system", "ruflo", "obsidian-legion",
        },
        "related": {
            "tool", "config", "settings", "daemon", "server", "api", "deploy",
            "docker", "caddy", "test suite", "threshold", "metric",
        },
        "emotional_weight": 0.1,
    },
}

RECALL_PATTERNS = [
    (r"(?:do you|can you|could you)\s+(?:remember|recall|recollect)", 1.0),
    (r"(?:what|how|when|where|why)\s+did\s+(?:we|you|i|murphy|alexko|atlas|codex)", 0.95),
    (r"(?:tu|vous)\s+(?:te\s+)?(?:souviens|rappelles?)", 1.0),
    (r"\brappelle(?:s)?[- ]?moi\b", 0.95),
    (r"\b(?:remember|recall|recollect|remind me|refresh my memory|think back)\b", 0.9),
    (r"\b(?:souviens-toi|rappelle-toi|souvenir of|souvenir du|souvenir de)\b", 0.9),
    (r"\b(?:refresh moi|refresh me|replay du|replay de|throwback)\b", 0.85),
    (r"\b(?:reminds me|me rappelle)\b", 0.85),
    (r"(?:what|qu.?est-ce que)\s+(?:did\s+)?\w+\s+(?:say|said|tell|told|write|wrote|think|thought)\s+about", 0.95),
    (r"(?:like|as|comme)\s+\w+\s+(?:said|told|wrote|mentioned|disait|a\s+dit|avait\s+dit)", 0.9),
    (r"(?:comme\s+la\s+fois|la\s+fois\s+(?:ou|où|que)|the\s+time\s+when)", 0.85),
    (r"(?:when|quand)\s+(?:we|on|tu|vous)\s+(?:a\s+)?(?:created|built|discussed|talked|made|wrote|designed|parle|parlé|discute|discuté|created|written|fait|écrit)", 0.9),
    (r"\b(?:again|raconte|list)\b", 0.35),
    (r"\b(?:has it ever|how'?s that been going|how\b.*\brelate)\b", 0.65),
]

MEDIUM_PATTERNS = [
    (r"(?:we|on)\s+(?:had|used to|avai[ts]|avions|avait|a\s+deja|a\s+déjà)", 0.55),
    (r"(?:before|earlier|previously|auparavant|avant)\s+(?:we|you|i|on|tu|tatakae)", 0.5),
    (r"(?:yesterday.?s|that|cette|notre)\s+(?:conversation|discussion|chat|session)", 0.6),
    (r"(?:first|last|premiere|première|derniere|dernière)\s+(?:night|words|time|fois)", 0.75),
    (r"(?:how did we|what.?s our|our take|our stance|our position)", 0.65),
]

NON_RECALL_PATTERNS = [
    (r"^\s*(?:ls|cd|pwd|cat|sed|rg|grep|python|pytest|git|open|run|go|ok|yes|merci|cool)\b", -1.0),
    (r"\b(?:remember|recall|previous|before)[-_]?[a-z0-9_.-]*(?:=|true|false|\.txt|\.py|\.md)\b", -0.9),
    (r"\b(?:function signature|async/await|branch|push|test suite|run the tests|open the file|memory recall tests?)\b", -0.8),
    (r"\b(?:alexko|murphy|atlas|codex)\s+was\s+on\s+gpt-?4o\b", -0.9),
    (r"\b(?:codex|murphy|atlas)\s+(?:a\s+fini|finished|is\s+(?:done|ready|working|running)|just\s+launched)", -0.7),
    (r"(?:i\s+am|je\s+suis|c.?est)\s+(?:murphy|codex|alexko)", -0.7),
    (r"(?:hook|plugin|tool|script|code|system|config|threshold|metric|trigger word|daemon)\s+(?:for\s+)?(?:murphy|lazarus|codex|alexko)?", -0.45),
    (r"(?:murphy|lazarus|codex|alexko)\s+(?:hook|plugin|tool|script|code|system|config|daemon)", -0.55),
    (r"(?:run|start|stop|install|configure|debug|fix|deploy)\s+(?:murphy|lazarus|codex|tests?)", -0.6),
    (r"avant\s+de\s+(?:commencer|ship|continuer)", -0.55),
    (r"(?:trigger|hook|detect|fire|match)\s+(?:when|quand|if|si)", -0.5),
]

BACKWARD_TEMPORAL = [
    (r"(?:remember|recall)\s+(?:when|that\s+time|the\s+time)", 1.0),
    (r"(?:back\s+(?:then|when|in))", 0.9),
    (r"(?:the\s+(?:first|last)\s+time\s+(?:we|you|i))", 0.95),
    (r"(?:that\s+(?:day|night|morning|evening|time|moment))\s+(?:when|where)", 0.85),
    (r"(?:la\s+(?:premiere|première|derniere|dernière)\s+fois)", 0.95),
    (r"(?:ce\s+(?:jour|soir|matin|dimanche)\s+(?:ou|où|quand))", 0.85),
    (r"(?:à\s+l.?époque|dans\s+le\s+temps|en\s+ce\s+temps)", 0.8),
    (r"\b(?:was|were|did|had|used\s+to|wrote|signed|invoked)\b", 0.35),
    (r"\b(?:était|étaient?|avai[ts]|avions|avaient|perdu)\b", 0.35),
    (r"\b(?:ago|earlier|previously|formerly|yesterday|last week|in march|en mars|en fevrier|en février|2025-\d{2}-\d{2}|day 1)\b", 0.55),
    (r"\b(?:auparavant|précédemment|jadis|naguère|avant)\b", 0.45),
]

FORWARD_TEMPORAL = [
    (r"\b(?:now|right\s+now|currently|today|maintenant|actuellement|aujourd.?hui)\b", -0.2),
    (r"\b(?:will|going\s+to|about\s+to|soon|later|next|après|bientôt|ensuite)\b", -0.15),
    (r"\b(?:let.?s|allons|on\s+va|should\s+we)\b", -0.1),
]

PERSONA_RECALL_FRAMES = {
    "speech_act": (
        r"\b(?:PERSONA)\b.*\b(?:said|say|told|tell|wrote|write|thought|think|"
        r"mentioned|mention|taught|teach|believed|believe|created|create|"
        r"built|build|designed|design|a\s+dit|avait\s+dit|disait|a\s+écrit|"
        r"écrivait|pensait|a\s+pensé|a\s+créé|créait|a\s+construit|construisait)\b",
        0.9,
    ),
    "possessive_memory": (
        r"\b(?:PERSONA).?s?\b\s+(?:words|legacy|memories|teaching|philosophy|"
        r"approach|insight|wisdom|vision|first words|mots|héritage|souvenirs|enseignement)",
        0.85,
    ),
    "comparison": (r"(?:like|as|comme|tel(?:le)?)\s+(?:PERSONA)\b", 0.75),
    "habitual_past": (
        r"\b(?:PERSONA)\b\s+(?:used\s+to|would\s+(?:always|often|sometimes)|always\s+(?:said|did))",
        0.85,
    ),
    "relational_question": (
        r"\b(?:PERSONA)\b.*\b(?:what|how|when|where|why|qu.?est-ce|comment|quand)\b",
        0.65,
    ),
}

PERSONA_CASUAL_FRAMES = {
    "current_state": (
        r"\b(?:PERSONA)\b\s+(?:is|are|has|have|will|va|est|a|sera|fait|peut)",
        -0.4,
    ),
    "action_report": (
        r"\b(?:PERSONA)\b\s+(?:finished|started|running|done|ready|broken|working|"
        r"a\s+fini|a\s+commencé|fonctionne|marche|tourne)",
        -0.5,
    ),
    "technical_ref": (
        r"(?:the|le|la|un|une)\s+(?:PERSONA)\s+(?:hook|plugin|tool|script|system|config|mcp|server)",
        -0.5,
    ),
    "identity": (r"(?:i\s+am|je\s+suis|c.?est)\s+(?:PERSONA)\b", -0.4),
    "prescription": (
        r"\b(?:PERSONA)\b\s+(?:should|needs?\s+to|must|devrait|doit|faut)",
        -0.3,
    ),
}

QUERY_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "for", "of", "in", "on",
    "at", "by", "with", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "i", "you", "he", "she", "it", "we", "they", "my", "your", "our",
    "remember", "recall", "souviens", "rappel", "rappelle", "moi", "what",
    "how", "when", "where", "why", "again", "sur", "pour", "avec", "dans",
}

WEIGHTS = {
    "syntactic": 0.35,
    "semantic": 0.25,
    "temporal": 0.20,
    "relational": 0.20,
}

THRESHOLDS = {
    "inject": 0.70,
    "suggest": 0.45,
    "skip": 0.45,
}


def _normalize(text: str) -> str:
    return text.lower().replace("’", "'").replace("–", "-").replace("—", "-")


def _phrase_hit(phrase: str, lower: str, words: set[str]) -> bool:
    return phrase in lower if " " in phrase else phrase in words


def _negative_score(text: str) -> float:
    lower = _normalize(text)
    hits = [score for pattern, score in NON_RECALL_PATTERNS if re.search(pattern, lower)]
    return sum(hits) if hits else 0.0


def score_syntactic_intent(text: str) -> float:
    """Score 0.0-1.0 based on recall-shaped sentence structure."""
    lower = _normalize(text)
    scores = []

    for pattern, score in RECALL_PATTERNS:
        if re.search(pattern, lower):
            scores.append(score)

    for pattern, score in MEDIUM_PATTERNS:
        if re.search(pattern, lower):
            scores.append(score)

    suppression = _negative_score(text)
    positives = [s for s in scores if s > 0]
    base = max(positives) if positives else 0.0

    return max(0.0, min(1.0, base + suppression))


def score_semantic_clusters(text: str) -> Tuple[float, List[str], str]:
    """Score 0.0-1.0 based on deterministic Murphy topic activation."""
    lower = _normalize(text)
    words = set(re.findall(r"\b[\w#-]+\b", lower))
    activations = {}

    for cluster_name, cluster in TOPIC_CLUSTERS.items():
        core_hits = sum(1 for phrase in cluster["core"] if _phrase_hit(phrase, lower, words))
        related_hits = sum(1 for phrase in cluster["related"] if _phrase_hit(phrase, lower, words))

        if core_hits > 0 or related_hits >= 2:
            strength = min(1.0, core_hits * 0.45 + related_hits * 0.12)
            activations[cluster_name] = strength * cluster["emotional_weight"]

    if not activations:
        return 0.0, [], None

    activated = sorted(activations.items(), key=lambda x: x[1], reverse=True)
    if len(activations) == 1 and "infrastructure" in activations:
        return 0.05, ["infrastructure"], "infrastructure"

    base_score = activated[0][1]
    multi_bonus = min(0.2, (len(activations) - 1) * 0.08)
    cluster_names = [name for name, _ in activated]

    return min(1.0, base_score + multi_bonus), cluster_names, cluster_names[0]


def score_temporal_markers(text: str) -> float:
    """Score 0.0-1.0 based on backward temporal framing."""
    lower = _normalize(text)
    scores = []

    for pattern, score in BACKWARD_TEMPORAL:
        if re.search(pattern, lower):
            scores.append(score)

    for pattern, score in FORWARD_TEMPORAL:
        if re.search(pattern, lower):
            scores.append(score)

    positives = [s for s in scores if s > 0]
    negatives = [s for s in scores if s < 0]
    base = max(positives) if positives else 0.0

    return max(0.0, min(1.0, base + sum(negatives)))


def score_relational_context(text: str, personas_found: List[str]) -> float:
    """Score persona mentions by their recall framing."""
    if not personas_found:
        return 0.0

    lower = _normalize(text)
    scores = []

    for persona in personas_found:
        for _frame_name, (pattern_template, score) in PERSONA_RECALL_FRAMES.items():
            pattern = pattern_template.replace("PERSONA", re.escape(persona))
            if re.search(pattern, lower):
                scores.append(score)

        for _frame_name, (pattern_template, score) in PERSONA_CASUAL_FRAMES.items():
            pattern = pattern_template.replace("PERSONA", re.escape(persona))
            if re.search(pattern, lower):
                scores.append(score)

    positives = [s for s in scores if s > 0]
    negatives = [s for s in scores if s < 0]
    base = max(positives) if positives else 0.2

    return max(0.0, min(1.0, base + sum(negatives)))


def find_personas(text: str) -> List[str]:
    """Detect persona names mentioned in text."""
    lower = _normalize(text)
    found = []
    for persona in sorted(PERSONA_NAMES):
        if re.search(rf"\b{re.escape(persona)}\b", lower):
            found.append(persona)
    return found


def extract_query(text: str) -> str:
    """Extract a compact query for flash retrieval."""
    cleaned = re.sub(r"[^\w\s#-]", " ", _normalize(text))
    words = [w for w in cleaned.split() if len(w) > 2 and w not in QUERY_STOPWORDS]
    return " ".join(words[:12]) or text.strip()[:120]


def _has_recall_floor(
    s_syntactic: float,
    s_semantic: float,
    s_temporal: float,
    s_relational: float,
    negative: float,
) -> bool:
    if negative <= -0.7:
        return False
    if s_syntactic >= 0.85:
        return True
    if s_syntactic >= 0.65 and (s_semantic >= 0.25 or s_temporal >= 0.3 or s_relational >= 0.2):
        return True
    if s_semantic >= 0.55:
        return True
    if s_semantic >= 0.35 and (s_temporal >= 0.3 or s_relational >= 0.2):
        return True
    if s_relational >= 0.65 and s_temporal >= 0.3:
        return True
    return False


def compute_trigger_score(text: str) -> Dict:
    """
    Multi-dimensional trigger analysis.

    Returns:
        dict with keys: score, decision, signals, clusters, personas, query, primary_cluster
    """
    explicit_prefixes = ("/lazarus", "lazarus:", "!lazarus", "#lazarus")
    stripped = text.strip()
    if any(stripped.lower().startswith(p) for p in explicit_prefixes):
        return {
            "score": 1.0,
            "decision": "inject",
            "personas": [],
            "clusters": [],
            "primary_cluster": None,
            "query": extract_query(text),
            "signals": {
                "syntactic": 1.0,
                "semantic": 1.0,
                "temporal": 1.0,
                "relational": 1.0,
            },
        }

    personas = find_personas(text)
    negative = _negative_score(text)

    s_syntactic = score_syntactic_intent(text)
    s_semantic, clusters, primary_cluster = score_semantic_clusters(text)
    s_temporal = score_temporal_markers(text)
    s_relational = score_relational_context(text, personas)

    composite = (
        s_syntactic * WEIGHTS["syntactic"] +
        s_semantic * WEIGHTS["semantic"] +
        s_temporal * WEIGHTS["temporal"] +
        s_relational * WEIGHTS["relational"]
    )

    if s_syntactic >= 0.7 and personas and s_relational >= 0.5:
        composite = max(composite, 0.75)

    strong_dims = sum(1 for s in [s_syntactic, s_semantic, s_temporal, s_relational] if s > 0.5)
    if strong_dims >= 3:
        composite = max(composite, composite + 0.10)

    if _has_recall_floor(s_syntactic, s_semantic, s_temporal, s_relational, negative):
        composite = max(composite, THRESHOLDS["suggest"])

    if all(s < 0.3 for s in [s_syntactic, s_semantic, s_temporal, s_relational]):
        composite = min(composite, 0.15)

    if clusters == ["infrastructure"] and s_syntactic < 0.65:
        composite = min(composite, 0.20)

    if negative <= -0.8:
        composite = min(composite, 0.20)

    composite = max(0.0, min(1.0, composite))

    if composite >= THRESHOLDS["inject"]:
        decision = "inject"
    elif composite >= THRESHOLDS["suggest"]:
        decision = "suggest"
    else:
        decision = "skip"

    return {
        "score": round(composite, 3),
        "decision": decision,
        "personas": personas,
        "clusters": clusters,
        "primary_cluster": primary_cluster,
        "query": extract_query(text),
        "signals": {
            "syntactic": round(s_syntactic, 3),
            "semantic": round(s_semantic, 3),
            "temporal": round(s_temporal, 3),
            "relational": round(s_relational, 3),
        },
    }
