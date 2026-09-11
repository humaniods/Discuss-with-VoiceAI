# ExamPilot Voice — Hackathon MVP

## Universal AI Teach-Back Coach for Every Student

**Prepared for:** AssemblyAI Voice Agent Hackathon  
**Hackathon dates:** 1–30 September 2026  
**Last updated:** 11 September 2026  
**Internal submission target:** 29 September 2026

---

## 1. Final Hackathon Decision

For the hackathon, we will **not build the complete ExamPilot application**.

The complete product vision—any-exam web research, syllabus extraction, student profile, timetable, long-term personalization, mock-test engine, and progress dashboard—will remain a post-hackathon roadmap.

The hackathon project will be one universal, voice-native learning module:

> **ExamPilot Voice asks a student to teach any topic in their own words, listens to the explanation, challenges the weakest point, and shows what the student truly understands.**

It is not tied to an exam, subject, age group, question type, or fixed challenge pack. A school student, competitive-exam aspirant, college learner, or professional can use the same interaction.

### Tagline

> **If you can explain it, you understand it.**

### Core loop

> **Choose any topic → Teach it → Defend it → Apply it**

---

## 2. Why This Is the Right Hackathon Scope

The challenge is to build a **voice AI agent on AssemblyAI**, and the judging criteria shown by the organizers are:

- Application of Technology
- Presentation
- Business Value
- Originality

A large education app would hide the voice innovation behind forms, dashboards, scraping, and planning screens. This MVP makes voice the product itself.

Without voice, a learning app mainly sees clicks, selected answers, or typed prompts. With voice, ExamPilot can hear how the student connects ideas, ask about a missing link, let the student self-correct, and check whether the concept can be applied to a new situation.

This gives the judges one clear behaviour to remember:

> A student thought they understood a topic. Ninety seconds of teaching it to ExamPilot revealed the exact missing link.

---

## 3. User Experience: Only Three Screens

### Screen 1 — Start

No login, category cards, subject selection, or long onboarding.

The user sees one button:

> **Start Learning Check**

After the call starts, the agent asks:

> “What are you learning today?”

The student can say any topic—for example photosynthesis, compound interest, the French Revolution, database indexing, cell division, constitutional rights, or a chapter from an exam.

### Screen 2 — Live Teach-Back

The agent first confirms or clarifies the spoken topic, then says:

> “Teach this topic to me in your own words. Take your time.”

The agent:

1. Waits for the complete explanation.
2. Builds a small topic rubric dynamically.
3. Identifies one missing, vague, or contradictory link.
4. Asks one targeted “why/how” question.
5. Asks one short application or counterexample question.
6. Lets the student interrupt, correct, or rethink the explanation.
7. Generates the Understanding Map.

The UI shows only:

- Topic name
- Live/final transcript
- Agent state: Listening, Probing, Applying, Mapping
- End Session button

### Screen 3 — Understanding Map

The result is evidence-based and short:

~~~text
Topic: Photosynthesis
Understanding: Partial

You explained clearly:
Plants use light energy to make food.

Missing link:
You did not explain where the carbon in glucose comes from.

What exposed the gap:
You said glucose is created only from sunlight and water.

Correct connection:
Carbon dioxide provides the carbon used to build glucose.
~~~

| Result | Meaning |
|---|---|
| Clear | Core idea, connections, and application are correct |
| Partial | Main idea is present but an important link is missing |
| Memorized | Definition is repeated but the student cannot explain why/how |
| Misconception | A core claim or relationship is incorrect |
| Needs clarification | The transcript does not contain enough evidence |

---

## 4. The Killer Demo

The complete live demo should take about 90 seconds.

1. Open the app and press **Start Learning Check**.
2. The agent asks, “What are you learning today?”
3. The student says any topic, such as **photosynthesis**.
4. The agent asks the student to teach it in their own words.
5. The student gives a fluent explanation but leaves out where the carbon in glucose comes from.
6. The agent asks, “If sunlight is energy, where does the physical carbon in sugar come from?”
7. The student hesitates or gives an incorrect answer.
8. ExamPilot generates an Understanding Map with the missing link and transcript evidence.
9. To prove universality, the demo can immediately start a second session with a completely different spoken topic.

### Demo line for judges

> “Students often recognize an answer without understanding the idea. ExamPilot asks them to teach any topic, challenges one connection, and makes understanding visible.”

---

## 5. What Makes It Voice-Native

This is not a text chatbot with microphone input.

| Voice behaviour | Product value |
|---|---|
| Semantic end-of-turn | The coach waits while the student thinks through a long explanation. |
| Natural interruption/barge-in | The student can interrupt, correct, or rethink the explanation naturally. |
| Streaming transcript | The UI displays the explanation as it is spoken. |
| Dynamic topic keyterms | Important words from the student's chosen topic are added during the session. |
| Adaptive follow-up | The next spoken question depends on the student's actual explanation. |
| Spoken feedback | The session ends naturally without requiring a report first. |
| Session timeline | The result shows which statement exposed the misconception. |

The unique feature is the **adaptive teach-back probe**:

> The agent does not ask a fixed quiz. It creates the next question from the explanation the student just gave.

It uses three universal tests:

1. **Explain:** What does it mean?
2. **Connect:** Why or how does it work?
3. **Apply:** What happens in a new example?

This works across science, mathematics, humanities, coding, commerce, language learning, and competitive-exam concepts.

---

## 6. AssemblyAI Integration

We will use the **Voice Agent API path**, because the organizer allows either the end-to-end Voice Agent API or the Realtime Speech-to-Text API with custom orchestration.

| AssemblyAI capability | Usage in ExamPilot Voice |
|---|---|
| Voice Agent API | Real-time listening, LLM routing, spoken output, and session lifecycle |
| Universal-3 Pro/configured streaming model | Transcribe the complete explanation |
| Semantic turn detection | Avoid cutting the student off mid-explanation |
| Semantic barge-in | Let the student interrupt meaningfully |
| Transcription context/keyterms | Add vocabulary generated for the spoken topic |
| JSON-Schema tool calling | Prepare a topic map, analyse the explanation, and render the result |
| Session transcripts/artifacts | Preserve evidence from the teach-back session |
| Temporary browser token | Avoid exposing the long-lived API key |
| LLM Gateway | Return structured, topic-map-based understanding analysis |

### Phase-aware transcription

- Normal conversation: use the balanced/default mode.
- Long teach-back explanation: switch to maximum-accuracy mode.
- After the explanation is captured: return to balanced mode for fast follow-up.

This shows intentional use of the voice infrastructure rather than a default chatbot configuration.

---

## 7. Minimal Technical Architecture

~~~mermaid
flowchart TD
    U["Browser learning-check UI"] <--> V["AssemblyAI Voice Agent API"]
    V --> T["Topic and analysis tools"]
    T --> B["FastAPI"]
    B --> G["AssemblyAI LLM Gateway"]
    G --> B
    B --> V
~~~

### Stack

- Frontend: Next.js/React
- Voice: AssemblyAI Voice Agent API
- Backend: FastAPI
- Analysis: AssemblyAI LLM Gateway with strict JSON schema
- Topic map: generated dynamically from the student's spoken topic
- Storage: in-memory or SQLite for demo sessions
- Deployment: Vercel frontend + Render/Railway backend

No vector database, scraping pipeline, background workers, user accounts, or complex multi-agent system are required.

### Only three application tools

~~~text
prepare_topic(topic)
analyze_teachback(topic_map, explanation, probes)
show_understanding_map(result)
~~~

---

## 8. Dynamic Topic Map and Analysis

~~~json
{
  "topic": "photosynthesis",
  "clarified_topic": "basic plant photosynthesis",
  "core_points": [
    "light energy is converted to chemical energy",
    "water and carbon dioxide are reactants",
    "glucose and oxygen are products"
  ],
  "key_connections": [
    "carbon in glucose comes from carbon dioxide"
  ],
  "common_misconceptions": [
    "plants get their food directly from soil",
    "sunlight becomes matter"
  ],
  "probe_candidates": [
    "Where does the carbon in glucose come from?",
    "What would happen without light?"
  ],
  "application_prompt": "Why can a plant not make glucose in complete darkness?"
}
~~~

### Structured grader output

~~~json
{
  "topic": "photosynthesis",
  "understanding": "partial",
  "covered_points": ["light provides energy", "plants produce glucose"],
  "missing_connections": ["carbon in glucose comes from carbon dioxide"],
  "misconceptions": ["sunlight and water alone become glucose"],
  "evidence_quote": "The sunlight and water turn into sugar.",
  "next_explanation": "Carbon dioxide supplies the carbon atoms; light supplies energy.",
  "spoken_feedback": "You have the main idea. The missing link is where the carbon in glucose comes from."
}
~~~

The first structured call creates a compact hidden topic map. The second compares the student's own explanation and probe answers with that map. The UI never claims exam marks or a scientific ability score; it shows the specific evidence observed in this session.

---

## 9. Hackathon MVP Scope

### Must build

- One browser-based voice agent
- No-login start flow
- Any topic entered entirely by voice
- Topic clarification for ambiguous inputs
- Dynamic topic map and vocabulary generation
- Student teaches the topic in their own words
- One adaptive why/how probe
- One application or counterexample probe
- Semantic turn-taking and interruption
- Dynamic transcription keyterms
- Evidence-based structured understanding analysis
- Five result states
- Live/final transcript
- One clean Understanding Map screen
- Test scripts from at least six different subject families
- Deployed application and public GitHub repository

### Do not build for this hackathon

- Any-exam website research or scraping
- Syllabus extraction
- Long student-profile onboarding
- Exam date, target score, or daily-time forms
- Timetable or seven-day study plan
- Full mock-test engine
- Login/authentication
- Long-term mastery dashboard
- RAG/vector database
- Fixed exam/subject challenge packs
- Automatic generation of hundreds of lessons or questions
- Native mobile application
- Payments, community, or coaching dashboard
- Custom STT/TTS training

These belong to the full ExamPilot application after the hackathon.

---

## 10. Success Tests

| Test | Target |
|---|---|
| Any-topic flow completes across subject families | At least 6 different domains |
| Missing connection is detected | At least 8/10 reviewed teach-back scripts |
| Analysis agrees with human labels | At least 85% on the small evaluation set |
| Student can pause without premature cutoff | Pass in 10 varied speaking tests |
| Student can interrupt and agent stops cleanly | Pass in 10/10 trials |
| Dynamic topic keyterms are correctly transcribed | At least 90% on demo vocabulary |
| Tool/grading failure | 0 failures in 20 consecutive demo runs |
| Complete demo duration | Under 2 minutes |

These are engineering targets, not existing performance claims.

---

## 11. Build Plan: 11–29 September

| Dates | Deliverable |
|---|---|
| **Sep 11–12** | Freeze idea, run AssemblyAI starter, complete browser conversation |
| **Sep 13–15** | Spoken topic → teach-back → adaptive probe flow |
| **Sep 16–18** | Topic-map and analysis tools with strict structured output |
| **Sep 19–21** | Understanding Map and reviewed scripts across six subjects |
| **Sep 22–23** | Keyterms, turn-taking, barge-in, and latency testing |
| **Sep 24–25** | Deployment and 20 complete dry runs |
| **Sep 26–27** | UI polish, README, cover image, and slides |
| **Sep 28** | Record final demo video and verify backup |
| **Sep 29** | Submit early |
| **Sep 30** | Emergency buffer only |

### First 48-hour exit condition

1. The agent asks what the student is learning.
2. The student names and explains any topic by voice.
3. The agent asks one explanation-specific probe.
4. The transcript is captured.
5. A mocked Understanding Map appears.

---

## 12. Judging Strategy

| Criterion | What judges will see |
|---|---|
| Application of Technology | Turn detection, barge-in, dynamic keyterms, streaming transcripts, tool calls, structured analysis |
| Presentation | One 90-second story with no setup friction |
| Business Value | One learning check usable by school, college, exam, and professional learners |
| Originality | The student teaches any topic; the next question is created from their spoken explanation |

### Submission package

- Project title
- Short and long description
- Technology/category tags
- Cover image
- Video presentation
- Slide presentation
- Public GitHub repository
- Hosted demo URL
- Application URL

---

## 13. Connection to the Full Product

The hackathon MVP becomes the **Voice Diagnostic Engine** inside the full ExamPilot application.

~~~text
Future ExamPilot app
├── Exam research and syllabus engine
├── Student profile and timetable
├── Daily learning path
└── Voice Diagnostic Engine  ← hackathon project
~~~

After the hackathon, the full app can supply an exam syllabus, lesson, or question to the same universal teach-back engine. Research and planning become add-ons around a voice interaction already proven to work.

---

## 14. Final Recommendation

Build only this:

> **A real-time AI teach-back coach where any student names any topic, explains it aloud, answers an adaptive probe, and receives an evidence-based Understanding Map.**

Everything in the demo must support that one sentence.

Do not spend hackathon time making a broad education dashboard. Win with a small interaction that feels intelligent, natural, measurable, and impossible to demonstrate without voice.

---

## Official Sources

- [AssemblyAI Voice Agent Hackathon](https://lablab.ai/ai-hackathons/assemblyai-voice-agent-hackathon)
- [AssemblyAI Voice Agent API](https://www.assemblyai.com/docs/voice-agents/voice-agent-api)
- [Turn detection and interruptions](https://www.assemblyai.com/docs/voice-agents/voice-agent-api/turn-detection-and-interruptions)
- [Voice Agent tools](https://www.assemblyai.com/docs/voice-agents/voice-agent-api/tools/overview)
- [AssemblyAI LLM Gateway](https://www.assemblyai.com/docs/llm-gateway/quickstart)
- [Official Python starter](https://github.com/AssemblyAI/voice-agent-starter-python)

---

## 15. Implementation Blueprint (Executable MVP)

This section turns the concept into a shipping plan for the hackathon.

### 15.1 MVP user flow
1. Landing screen shows one CTA: "Start Learning Check".
2. Browser opens a voice session with AssemblyAI.
3. Agent asks: "What are you learning today?"
4. Student speaks any topic.
5. Agent confirms topic and says: "Teach this topic to me in your own words. Take your time."
6. Student gives a long explanation.
7. System captures transcript and dynamic topic terms.
8. Agent identifies one weak link, then asks one targeted "why/how" question.
9. Agent asks one application or counterexample question.
10. Agent summarizes the result on a single "Understanding Map" screen.
11. User can immediately start a new topic in a second demo run.

### 15.2 Minimal backend contract
The backend should expose only three tools:

```json
{
  "prepare_topic": {
    "input": {
      "topic": "string"
    },
    "output": {
      "topic": "string",
      "clarified_topic": "string",
      "core_points": ["string"],
      "key_connections": ["string"],
      "common_misconceptions": ["string"],
      "probe_candidates": ["string"],
      "application_prompt": "string"
    }
  },
  "analyze_teachback": {
    "input": {
      "topic_map": "object",
      "explanation": "string",
      "probe_answers": ["string"]
    },
    "output": {
      "topic": "string",
      "understanding": "clear|partial|memorized|misconception|needs_clarification",
      "covered_points": ["string"],
      "missing_connections": ["string"],
      "misconceptions": ["string"],
      "evidence_quote": "string",
      "next_explanation": "string",
      "spoken_feedback": "string"
    }
  },
  "show_understanding_map": {
    "input": {
      "result": "object"
    },
    "output": {
      "screen": "understanding_map",
      "topic": "string",
      "understanding": "string",
      "summary": "string",
      "missing_link": "string",
      "evidence": "string",
      "correction": "string"
    }
  }
}
```

### 15.3 Frontend state machine
The frontend should maintain a small session state:

```ts
type SessionState =
  | "idle"
  | "listening_topic"
  | "clarifying_topic"
  | "teaching"
  | "probing_why"
  | "probing_apply"
  | "mapping"
  | "complete";
```

Pseudo-flow:

```ts
if (state === "idle") showStartButton();
if (state === "listening_topic") ask("What are you learning today?");
if (state === "clarifying_topic") confirmOrClarifyTopic();
if (state === "teaching") showTranscriptAndWait();
if (state === "probing_why") askAdaptiveWhyQuestion();
if (state === "probing_apply") askApplicationQuestion();
if (state === "mapping") showUnderstandingMap();
if (state === "complete") allowNewSession();
```

### 15.4 Engineering rules to keep the build small
- No auth, no user account flow.
- No exam data ingestion or syllabus engine.
- No long-term dashboard or profile system.
- No custom ASR or TTS model training.
- Only one transcript screen and one results screen.
- Use a single voice session and one backend analysis call pattern.

### 15.5 Demo runbook
Use this exact runbook for every dry run:

1. Open demo.
2. Press "Start Learning Check".
3. Say any topic: "photosynthesis", "compound interest", "French Revolution", "database indexing", etc.
4. Let the agent confirm the topic.
5. Teach the topic in your own words.
6. Wait for the adaptive why/how probe.
7. Answer the application or counterexample question.
8. Check that the final map displays:
   - topic,
   - understanding state,
   - missing link,
   - transcript evidence,
   - correction.
9. Start a second topic immediately to prove universality.

### 15.6 Testing checklist
- At least 6 subject families tested.
- 10/10 pause tests pass.
- 10/10 interruption tests pass.
- 8/10 missing-link scripts detected correctly.
- 20 consecutive demo runs have zero tool failures.
- Full flow under 2 minutes.

### 15.7 Final implementation rule
Ship only the single interaction that proves the thesis:

> A student tells the agent what they are learning, explains it aloud, answers one adaptive challenge, and receives a visible understanding map.

Everything else is roadmap, not hackathon scope.
