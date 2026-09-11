"""
The 3 tools from the plan (section 15.2 / section 7):

    prepare_topic(topic)                                 -> TopicMap
    analyze_teachback(topic_map, explanation, probes)     -> AnalyzeTeachbackOut
    show_understanding_map(result)                        -> UnderstandingMapOut

Each one tries the real LLM Gateway first (unless MOCK_MODE), and falls back
to a deterministic heuristic on any failure -- per the plan's own success
metric ("Tool/grading failure: 0 failures in 20 consecutive demo runs"), a
tool call must never dead-end the voice session.
"""
import re
from pydantic import ValidationError

import config
from llm_gateway import chat_json, LLMGatewayError
from schemas import TopicMap, AnalyzeTeachbackOut, UnderstandingMapOut

# ---------------------------------------------------------------------------
# A handful of canned topic maps covering the plan's "6 subject families"
# (section 9 / 15.6), used by the offline heuristic path so MOCK_MODE demos
# are actually good, not just non-empty.
# ---------------------------------------------------------------------------

_CANNED_TOPIC_MAPS = {
    "photosynthesis": TopicMap(
        topic="photosynthesis",
        clarified_topic="basic plant photosynthesis",
        core_points=[
            "light energy is converted to chemical energy",
            "water and carbon dioxide are reactants",
            "glucose and oxygen are products",
        ],
        key_connections=["carbon in glucose comes from carbon dioxide"],
        common_misconceptions=[
            "plants get their food directly from soil",
            "sunlight becomes matter",
        ],
        probe_candidates=[
            "Where does the carbon in glucose come from?",
            "What would happen without light?",
        ],
        application_prompt="Why can a plant not make glucose in complete darkness?",
    ),
    "compound interest": TopicMap(
        topic="compound interest",
        clarified_topic="compound interest on a principal amount",
        core_points=[
            "interest is earned on the principal",
            "each period's interest is added back to the principal",
            "future interest is earned on previous interest too",
        ],
        key_connections=["compounding grows the base amount every period, unlike simple interest"],
        common_misconceptions=[
            "compound interest grows at a constant amount each year",
            "compound interest and simple interest give the same total over time",
        ],
        probe_candidates=[
            "Why does compound interest overtake simple interest as time passes?",
            "What happens to the growth rate if the compounding period is shorter?",
        ],
        application_prompt="If you compound monthly instead of yearly at the same rate, does the total go up or down?",
    ),
    "french revolution": TopicMap(
        topic="french revolution",
        clarified_topic="causes of the French Revolution",
        core_points=[
            "France faced a severe financial crisis before 1789",
            "the Estates-General and Third Estate had unequal power",
            "Enlightenment ideas questioned absolute monarchy",
        ],
        key_connections=["the financial crisis and unequal taxation pushed the Third Estate to demand political change"],
        common_misconceptions=[
            "the revolution happened only because of the king's personality",
            "it was a single sudden event rather than a build-up of causes",
        ],
        probe_candidates=[
            "How did the financial crisis connect to the demands of the Third Estate?",
            "What role did Enlightenment thinking play before any fighting started?",
        ],
        application_prompt="If the king had reformed taxation in 1787, would the same revolution likely still happen?",
    ),
    "database indexing": TopicMap(
        topic="database indexing",
        clarified_topic="how a database index speeds up queries",
        core_points=[
            "an index is a separate data structure that maps values to row locations",
            "indexes avoid scanning every row (full table scan)",
            "indexes speed up reads but add overhead on writes",
        ],
        key_connections=["the query planner only uses an index when it matches the query's filter/sort columns"],
        common_misconceptions=[
            "adding an index always makes every query faster",
            "indexes are free to maintain",
        ],
        probe_candidates=[
            "Why doesn't an index help a query that filters on a different column?",
            "Why can too many indexes slow down writes?",
        ],
        application_prompt="You add an index on column A, but a query filtering on column B is still slow -- why?",
    ),
    "cell division": TopicMap(
        topic="cell division",
        clarified_topic="mitosis (somatic cell division)",
        core_points=[
            "DNA is replicated before division",
            "chromosomes separate into two identical sets",
            "one cell becomes two genetically identical daughter cells",
        ],
        key_connections=["replication must happen before separation, or daughter cells would get incomplete DNA"],
        common_misconceptions=[
            "cell division happens without copying the DNA first",
            "the two daughter cells can end up genetically different",
        ],
        probe_candidates=[
            "What would go wrong if a cell divided without replicating its DNA first?",
            "Why are the two daughter cells identical?",
        ],
        application_prompt="A cell skips DNA replication but still divides -- what happens to each daughter cell?",
    ),
    "newton's laws": TopicMap(
        topic="newton's laws",
        clarified_topic="Newton's second law (F = ma)",
        core_points=[
            "force causes acceleration, not velocity directly",
            "acceleration is proportional to net force",
            "acceleration is inversely proportional to mass",
        ],
        key_connections=["a constant force produces less acceleration on a more massive object"],
        common_misconceptions=[
            "force is required to keep something moving at constant velocity",
            "a bigger object always needs a bigger force to move at all",
        ],
        probe_candidates=[
            "Why does the same push accelerate a light cart faster than a heavy one?",
            "Why can an object move at constant velocity with zero net force?",
        ],
        application_prompt="You push two carts with the same force; one is twice as heavy. How do their accelerations compare?",
    ),
}

_GENERIC_MISCONCEPTIONS = [
    "treating a description of {t} as the same thing as explaining why it happens",
    "assuming {t} has a single cause with no supporting mechanism",
]


def _generic_topic_map(topic: str) -> TopicMap:
    t = topic.strip().lower()
    return TopicMap(
        topic=t,
        clarified_topic=t,
        core_points=[
            f"the basic definition of {t}",
            f"the mechanism or process that makes {t} happen",
            f"a real consequence or output of {t}",
        ],
        key_connections=[f"why the mechanism behind {t} produces its observed outcome"],
        common_misconceptions=[m.format(t=t) for m in _GENERIC_MISCONCEPTIONS],
        probe_candidates=[
            f"Why does {t} work the way it does, not just what it is?",
            f"What would change if a key condition behind {t} were removed?",
        ],
        application_prompt=f"Give a new example where {t} applies, and explain why it applies.",
    )


def _heuristic_topic_map(topic: str) -> TopicMap:
    key = topic.strip().lower()
    for canned_key, tm in _CANNED_TOPIC_MAPS.items():
        if canned_key in key or key in canned_key:
            return tm
    return _generic_topic_map(topic)


_WORD_RE = re.compile(r"[a-zA-Z']+")


def _keywords(phrase: str) -> set:
    stop = {"the", "a", "an", "is", "are", "of", "to", "in", "and", "or", "on", "that", "this", "it", "its", "not", "for"}
    return {w for w in _WORD_RE.findall(phrase.lower()) if w not in stop and len(w) > 2}


def _phrase_present(phrase: str, text: str) -> bool:
    """Loose containment: most of the phrase's keywords show up in the text."""
    kws = _keywords(phrase)
    if not kws:
        return False
    text_words = _keywords(text)
    hits = sum(1 for k in kws if k in text_words)
    return hits / len(kws) >= 0.6


def _heuristic_analyze(topic_map: TopicMap, explanation: str, probe_answers: list) -> AnalyzeTeachbackOut:
    full_text = " ".join([explanation, *probe_answers])
    word_count = len(_WORD_RE.findall(explanation))

    covered = [p for p in topic_map.core_points if _phrase_present(p, full_text)]
    missing_conns = [c for c in topic_map.key_connections if not _phrase_present(c, full_text)]
    hit_misconceptions = [m for m in topic_map.common_misconceptions if _phrase_present(m, explanation)]

    if word_count < 12:
        understanding = "needs_clarification"
    elif hit_misconceptions:
        understanding = "misconception"
    elif not covered:
        understanding = "memorized"
    elif not missing_conns:
        understanding = "clear"
    else:
        understanding = "partial"

    evidence = explanation.strip()[:180] or "(no explanation captured)"
    missing_text = missing_conns[0] if missing_conns else "no missing connection detected"

    spoken = {
        "clear": f"You explained {topic_map.clarified_topic} clearly, including the key connection.",
        "partial": f"You have the main idea of {topic_map.clarified_topic}. The missing link is: {missing_text}.",
        "memorized": f"You repeated the definition of {topic_map.clarified_topic}, but I could not hear why or how it works.",
        "misconception": f"One part of what you said about {topic_map.clarified_topic} is incorrect: {hit_misconceptions[0] if hit_misconceptions else ''}",
        "needs_clarification": f"I did not get enough of an explanation of {topic_map.clarified_topic} to judge understanding yet.",
    }[understanding]

    return AnalyzeTeachbackOut(
        topic=topic_map.topic,
        understanding=understanding,
        covered_points=covered,
        missing_connections=missing_conns,
        misconceptions=hit_misconceptions,
        evidence_quote=evidence,
        next_explanation=topic_map.key_connections[0] if topic_map.key_connections else "",
        spoken_feedback=spoken,
    )


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------

async def prepare_topic(topic: str) -> TopicMap:
    if not config.MOCK_MODE:
        try:
            system = (
                "You are the topic-mapping module of ExamPilot Voice, a teach-back "
                "learning coach. Given any spoken topic (any subject, any level), "
                "produce a compact hidden topic map used later to grade a student's "
                "own explanation. Respond with ONLY a JSON object with exactly these "
                "keys: topic, clarified_topic, core_points (3-5 short strings), "
                "key_connections (1-3 short strings describing WHY/HOW things connect, "
                "not just what they are), common_misconceptions (1-3 strings), "
                "probe_candidates (2 short why/how questions), application_prompt "
                "(1 new-situation question)."
            )
            data = await chat_json(system, f"Topic: {topic}")
            return TopicMap.model_validate(data)
        except (LLMGatewayError, ValidationError):
            pass  # fall through to heuristic -- never fail the tool call
    return _heuristic_topic_map(topic)


async def analyze_teachback(topic_map: TopicMap, explanation: str, probe_answers: list) -> AnalyzeTeachbackOut:
    if not config.MOCK_MODE:
        try:
            system = (
                "You are the grading module of ExamPilot Voice. Compare the "
                "student's spoken explanation (and their answers to follow-up "
                "probes) against the hidden topic map. Respond with ONLY a JSON "
                "object with exactly these keys: topic, understanding (one of "
                "clear|partial|memorized|misconception|needs_clarification), "
                "covered_points (subset of core_points actually explained), "
                "missing_connections (subset of key_connections not explained), "
                "misconceptions (subset of common_misconceptions the student's "
                "words match), evidence_quote (a short verbatim quote from the "
                "explanation that best shows the gap or strength), "
                "next_explanation (one sentence giving the missing connection), "
                "spoken_feedback (1-2 short sentences, said aloud to the student)."
            )
            user = (
                f"Topic map: {topic_map.model_dump_json()}\n"
                f"Student explanation: {explanation}\n"
                f"Probe answers: {probe_answers}"
            )
            data = await chat_json(system, user)
            return AnalyzeTeachbackOut.model_validate(data)
        except (LLMGatewayError, ValidationError):
            pass
    return _heuristic_analyze(topic_map, explanation, probe_answers)


async def show_understanding_map(result: AnalyzeTeachbackOut) -> UnderstandingMapOut:
    # Pure transform -- no model call, matches the plan's tool signature.
    summary = "; ".join(result.covered_points) if result.covered_points else "no core point confirmed yet"
    missing_link = result.missing_connections[0] if result.missing_connections else (
        result.misconceptions[0] if result.misconceptions else "none -- explanation was complete"
    )
    return UnderstandingMapOut(
        topic=result.topic,
        understanding=result.understanding,
        summary=summary,
        missing_link=missing_link,
        evidence=result.evidence_quote,
        correction=result.next_explanation,
    )
