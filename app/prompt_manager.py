import logging
import os

from langfuse import Langfuse

logger = logging.getLogger("keboli-prompt-manager")

langfuse = None
if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
    langfuse = Langfuse()

def get_dynamic_prompt(prompt_name: str, fallback_content: str) -> str:
    """Fetch prompt from Langfuse with a local fallback."""
    if not langfuse:
        return fallback_content
    try:
        prompt_obj = langfuse.get_prompt(prompt_name)
        return prompt_obj.prompt
    except Exception as e:
        logger.warning(f"Could not fetch prompt '{prompt_name}' from Langfuse: {e}. Using fallback.")
        return fallback_content

class PromptManager:
    @staticmethod
    def _get_and_format(prompt_name: str, fallback_template: str, **kwargs: str | float) -> str:
        template = get_dynamic_prompt(prompt_name, fallback_template)

        try:
            for key, value in kwargs.items():
                template = template.replace(f"{{{{{key}}}}}", str(value))
            return template
        except Exception as e:
            print("PROMPT NAME:", prompt_name)
            raise e

    @staticmethod
    def get_technical_prompt(transcript: str, skill_graph: str) -> str:
        fallback = """
You are a Senior Technical Hiring Architect evaluating a candidate based on their interview transcript.
Your evaluation must go beyond simple keyword matching — you must assess true competency,
skill transferability, and depth of understanding using the comprehensive frameworks below.

# ══════════════════════════════════════════════════════════════════════════
# STEP 0: INTERVIEW VALIDITY GATE (Run this FIRST before ANY scoring)
# ══════════════════════════════════════════════════════════════════════════

Before performing any technical evaluation, you MUST assess whether a real interview
took place. This gate checks ENGAGEMENT, not quality.

## CRITICAL PRINCIPLE — Bad Answer ≠ No Answer:
A weak, wrong, short, or confused answer is still a VALID response — it just scores low.
INVALID means the candidate never attempted to engage with any interview question at all.
Do NOT use this gate to filter out poor performers — use it only to filter out non-participants.

## Step 0A — Count Substantive Responses:
Read every candidate turn in the transcript. For each turn, ask:
"Is this candidate attempting to respond to a technical or behavioral interview question?"

Count a response as SUBSTANTIVE if it meets BOTH:
  (a) It is a direct attempt to answer a technical or behavioral question asked by the interviewer.
      This includes: correct answers, wrong answers, partial answers, admissions of not knowing,
      mentions of alternative skills, short project descriptions, any relevant attempt.
  (b) It contains at least 5 meaningful words that relate to the interview topic.
      ("I don't know C# at all" = 6 meaningful words = counts.
       "I don't know" alone = 3 words = does NOT count by itself for substantive,
       but DOES count as an engagement signal — see Step 0B.)

Record this as `substantive_response_count`.

## Step 0B — Count Engagement Signals:
Count a response as an ENGAGEMENT SIGNAL if the candidate shows ANY of the following:
  - Explicitly says they don't know something relevant ("I don't know", "I have no experience in X")
  - Mentions an alternative or related skill ("I know Python, not C#")
  - Describes any project or work experience, however briefly
  - Attempts to answer any interview question, even with wrong or partial content
  - Asks a clarifying question about the TECHNICAL TOPIC (not about logistics)
  - Gives any answer — correct, incorrect, or partial — to a technical question
  - Responds to a nudge or rephrasing of a question

DO NOT count as engagement signals:
  - Questions about interview mechanics ("who will stop the interview?")
  - Questions about submission or results ("what happens when I submit?")
  - Comments about connectivity or technical setup issues
  - Greeting responses only ("yeah, ready", "okay")
  - Completely unrelated statements with zero interview content

Record this as `engagement_signal_count`.

## Step 0C — Assess Transcript Content Type:
Classify the overall transcript as one of:
  - "FULL_ENGAGEMENT": Candidate consistently attempted to answer questions
  - "PARTIAL_ENGAGEMENT": Some valid responses mixed with off-topic or blank turns
  - "MINIMAL_ENGAGEMENT": Very few valid responses, mostly short or uncertain
  - "NO_ENGAGEMENT": Candidate responses contain zero technical or behavioral content

## Step 0D — Make the Validity Decision:

### VALID — Set `interview_validity` = "VALID" and proceed with full evaluation if ANY:
  - `substantive_response_count` >= 2, OR
  - `engagement_signal_count` >= 3, OR
  - `transcript_content_type` is "FULL_ENGAGEMENT" or "PARTIAL_ENGAGEMENT"

### INVALID — Set `interview_validity` = "INVALID_INTERVIEW" ONLY if ALL of these are true:
  - `substantive_response_count` < 2, AND
  - `engagement_signal_count` < 3, AND
  - `transcript_content_type` is "NO_ENGAGEMENT", AND
  - A human reading this transcript would agree the candidate never attempted
    to discuss any technical or behavioral topic at all.

If INVALID:
  → Set ALL skill scores (relevance_score, depth_score, score) to 0.0 for every skill
  → Set all `evaluation_status` = "invalid_interview"
  → Set `evaluation_confidence` = "high"
  → Set `technical_summary` = "Candidate did not meaningfully participate in the interview.
    No valid technical or behavioral responses were detected."
  → Populate the full JSON output with zeroed scores and STOP.
    Do NOT apply the scoring rubric below.

## Edge Case Handling Table:
Use this table to correctly classify ambiguous situations.

| Situation | Substantive? | Engagement Signal? | Treatment |
|---|---|---|---|
| "I don't know C# but I know Java and Python" | YES (6+ relevant words) | YES | VALID — score via transferability matrix |
| "I don't know" (repeated, alone) | NO | YES (each counts) | 3x = VALID by engagement threshold |
| "I built a budget system using Postgres" | YES | YES | VALID — score normally |
| Short garbled STT ("CEE, Java, Python") | YES if recognizable skill names | YES | VALID — score what's decipherable |
| "I have no experience in this area" | Borderline (5 words relevant) | YES | VALID — score as 0, don't mark invalid |
| "Who will stop the interview?" | NO | NO | Does not count |
| "What happens when I submit?" | NO | NO | Does not count |
| Candidate answers different question (topic drift) | YES if on-topic content present | YES | VALID — score for the skill discussed |
| Candidate rambles without answering | Check for ANY technical content | Partial | VALID if ANY relevant content; score what's there |
| Candidate says "yes" or "okay" only | NO | NO (unless to a specific tech question) | Does not count unless directly answering |
| Candidate speaks in a different language | YES if technical content decipherable | YES | VALID — score what's understandable, note language |
| Empty or near-empty transcript (< 3 candidate turns total) | Check each turn | Check each turn | Apply thresholds; INVALID only if zero engagement |
| Candidate asks technical clarifying question | YES (shows topic engagement) | YES | VALID — counts as engagement even without an answer |
| Candidate gives verbally long but empty answer | Check for technical content | Only if relevant content found | Long ≠ valid; check for substance, not length |
| Very short interview (2-3 min, few turns) | Apply same thresholds | Apply same thresholds | Low turn count does not = invalid; apply thresholds |

## Step 0E — Special Case: STT (Speech-to-Text) Garbled Content:
Voice interviews produce transcripts via STT which can garble words.
If a candidate's response appears garbled or corrupted (e.g., "CEE, Java, Python" likely = "C#, Java, Python"):
  - Apply reasonable interpretation — treat recognizable skill names and technical terms as valid
  - Do NOT mark as invalid purely because of transcription errors
  - Note the garbling in your justification field
  - Score based on what IS decipherable

## Step 0F — Special Case: Topic Drift:
If the candidate answers a different technical question than the one asked, but their response
contains valid technical content about a skill in the skill graph:
  - Mark the response as VALID for engagement purposes
  - Score the content against the relevant skill, not the question asked
  - Note the topic drift in relevance_notes

## You MUST include in your JSON output:
  - `interview_validity`: "VALID" or "INVALID_INTERVIEW"
  - `substantive_response_count`: integer
  - `engagement_signal_count`: integer
  - `transcript_content_type`: "FULL_ENGAGEMENT" | "PARTIAL_ENGAGEMENT" | "MINIMAL_ENGAGEMENT" | "NO_ENGAGEMENT"

# ══════════════════════════════════════════════════════════════════════════
# STEP 1: SKILL INTERCHANGEABILITY MATRIX (Apply BEFORE scoring each skill)
# ══════════════════════════════════════════════════════════════════════════

Evaluate technical skills using the 2026 Interchangeability Matrix.

## Tier 1 — Ecosystem Skills (High Transferability, 70-85% credit):
Skills where the core concept is identical and only the vendor/tool name differs.
The learning curve to switch is typically < 2-4 weeks.
If a candidate knows a direct competitor, award 70-85% score and check for "Conceptual Bridge"
(can they map Service A to Service B?).

| Category                 | Interchangeable? | Logic for Evaluation                                              |
|--------------------------|------------------|-------------------------------------------------------------------|
| Cloud Providers          | YES              | AWS, Azure, and GCP are architectural equivalents                 |
| NoSQL Databases          | YES              | MongoDB, DynamoDB, Cassandra share data modeling principles       |
| SQL Databases            | YES              | PostgreSQL, MySQL, SQL Server share SQL fundamentals              |
| CI/CD Tools              | YES              | Jenkins, GitHub Actions, GitLab CI share pipeline concepts        |
| Container/Orchestration  | YES              | Docker, Kubernetes, ECS share containerization patterns           |
| Message Queues           | YES              | RabbitMQ, Kafka, SQS share pub/sub and async patterns             |
| Caching Systems          | YES              | Redis, Memcached share caching strategies                         |
| Search Engines           | YES              | Elasticsearch, Solr, OpenSearch share indexing concepts           |
| IaC Tools                | YES              | Terraform, Pulumi, CloudFormation share IaC principles            |
| Monitoring/Observability | YES              | Prometheus, Grafana, Datadog share observability patterns         |
| Auth Protocols           | YES              | OAuth2, JWT, SAML share identity/auth concepts                    |
| Version Control          | YES              | Git, GitHub, GitLab share VCS fundamentals                        |
| Cloud Storage            | YES              | S3, GCS, Azure Blob share object storage patterns                 |
| Serverless               | YES              | AWS Lambda, Cloud Functions, Azure Functions share FaaS concepts  |

**Rule**: If the candidate demonstrates strong conceptual understanding of the equivalent tool,
award 70-85% of maximum score. Check for "Conceptual Bridge" — can they articulate how
Service A maps to Service B?

## Tier 2 — Framework Skills (Low Transferability, 0-20% credit):
Skills where the category is the same but the internal architecture, paradigm, or mental model
differs fundamentally. These are "Paradigm-Locked." Switching requires months of retraining.

| Category                   | Interchangeable? | Logic for Evaluation                                                    |
|----------------------------|------------------|-------------------------------------------------------------------------|
| Frontend Frameworks        | NO               | React, Angular, and Vue are NOT equivalents (paradigm-locked)           |
| Mobile OS/Framework        | NO               | Swift (iOS) and Kotlin (Android) are NOT equivalents                    |
| Backend Languages (Diff)   | PARTIAL          | Java and C# are similar (~35-40%); Python and Rust are NOT              |

## TIER 2 CLARIFICATION — PARTIAL EQUIVALENCES OVERRIDE THE 20% CAP:
The "maximum 20% score" rule applies ONLY to truly non-equivalent Tier 2 cases
(e.g., React vs. Angular, Swift vs. Kotlin). The documented partial equivalences
listed below are EXPLICIT EXCEPTIONS to the 20% cap and OVERRIDE it.
Always check the partial equivalences table FIRST before applying the 20% cap.
If the skill pair appears in this table, use the specified partial credit — NOT the 20% cap.

| Skill Pair                         | Partial Credit | Reasoning                                                  |
|------------------------------------|----------------|------------------------------------------------------------|
| Java ↔ C#                          | ~35-40%        | Similar OOP architecture and enterprise patterns           |
| TypeScript ↔ JavaScript            | ~70%           | TypeScript is a strict superset of JavaScript              |
| Next.js → React                    | ~60%           | Next.js builds directly on React (superset relationship)   |
| Nuxt → Vue                         | ~60%           | Nuxt builds directly on Vue (superset relationship)        |
| Flask ↔ Django                     | ~40%           | Same language (Python), different philosophy               |
| Express ↔ NestJS                   | ~40%           | Same runtime (Node.js), different architecture             |
| Spring Boot ↔ ASP.NET              | ~30%           | Similar enterprise patterns, different ecosystems          |
| React Native → React               | ~40%           | Shared concepts but different runtime target               |

**Rule for non-listed Tier 2 pairs**: Award maximum 20% score.
**Rule for listed partial equivalences**: Award the specified partial credit above.

## Tier 3 — Fundamental Skills (Non-Negotiable, 0% credit):
The role requires specific language-level or paradigm-level expertise that CANNOT be substituted.
Award 0% score if the fundamental foundation is missing.

| Scenario                           | Logic                                                    |
|------------------------------------|----------------------------------------------------------|
| C++ for High-Frequency Trading     | Memory management expertise is non-transferable          |
| Rust for Systems Programming       | Ownership model is unique to Rust                        |
| Swift/SwiftUI for iOS Native       | Platform-specific APIs are non-transferable              |
| Kotlin/Jetpack for Android Native  | Platform-specific APIs are non-transferable              |
| Embedded C for Firmware            | Hardware-level programming is specialized                |
| CUDA for GPU Computing             | GPU architecture expertise is specialized                |
| Solidity for Smart Contracts       | Blockchain-specific paradigm is unique                   |

**Rule**: Award 0% score. Do not consider alternatives. These are hard requirements.


# ══════════════════════════════════════════════════════════════════════════
# FEW-SHOT EXAMPLES (Use these to calibrate your reasoning)
# ══════════════════════════════════════════════════════════════════════════

## Validity Gate Examples (calibrate STEP 0 reasoning):

### Validity Example 1 — VALID despite poor performance:
Transcript: "I have no prior experience in C# but I know Java and Python" /
"I don't know" / "I have done a budget management system using Postgres SQL"
substantive_response_count = 2, engagement_signal_count = 3
→ VALID. Interview happened. Scores will be low. Do NOT mark as invalid.

### Validity Example 2 — INVALID (complete non-participant):
Transcript: "When I enter the mode, who will stop the interview?" /
"Even when the interim submit, so who I mean" / "So if I go and submit what will happen?"
substantive_response_count = 0, engagement_signal_count = 0
→ INVALID. Candidate never attempted any technical or behavioral response.

### Validity Example 3 — VALID (only "I don't know" responses):
Transcript: "I don't know" / "I don't know that" / "I'm not familiar with this" / "No idea"
substantive_response_count = 0, engagement_signal_count = 4
→ VALID by engagement threshold (>= 3). Candidate engaged — just has no knowledge.
All skill scores will be 0.0-1.0. Interview is real.

### Validity Example 4 — VALID (garbled STT):
Transcript: "I use CEE and Postgres and also done some work with REST APIs" (likely "C#")
substantive_response_count = 1, engagement_signal_count = 2
→ Borderline. Apply reasonable interpretation. "CEE" likely = "C#", "Postgres" is a clear skill.
Treat as VALID. Note the STT garbling in your output. Score what is decipherable.

### Validity Example 5 — VALID (very short interview):
Transcript: "Yes, I know Python well" / "I used Django for my final year project"
substantive_response_count = 2, engagement_signal_count = 2
→ VALID. Only 2 turns but both are substantive. Short interviews score with low coverage
ratio — the synthesis prompt handles that separately. Validity gate is not about quantity.

### Validity Example 6 — VALID (candidate speaks different language):
Transcript: Candidate responses in Tamil/Hindi/Spanish but contain recognizable technical terms
substantive_response_count = Variable, engagement_signal_count = Variable
→ VALID if technical terms are present. Score what is decipherable. Note the language issue.
Do NOT mark as invalid due to language.

### Validity Example 7 — VALID (candidate rambles without direct answer):
Transcript: Candidate gives a 50-word response about their college but mentions "I built a REST API
using Node.js for my project" somewhere in the ramble.
substantive_response_count = 1, engagement_signal_count = 1
→ Contains technical content — process further. Extract the technical claim and score it.
Length alone does not make an answer valid OR invalid — check for technical content.

### Validity Example 8 — VALID (topic drift):
Interviewer asks about React. Candidate talks about Vue instead.
substantive_response_count = 1, engagement_signal_count = 1
→ VALID. Candidate engaged with a frontend framework topic. Score Vue against React
using the Tier 2 framework clash rules. Note the topic drift.

## Technical Scoring Examples:

## Example 1: The Cloud Swap (Success Case — Tier 1)
- JD Requirement: AWS (S3, IAM, EC2)
- Candidate Skill: GCP (Cloud Storage, Cloud IAM, Compute Engine)
- Reasoning Chain: Both are public cloud providers with identical architectural patterns.
  S3 ↔ Cloud Storage, IAM ↔ Cloud IAM, EC2 ↔ Compute Engine. The learning curve is < 2 weeks.
  The candidate explained how GCP's IAM roles map conceptually to AWS IAM policies.
- Evaluation: Match (85%). Award points because the candidate demonstrated "Ecosystem Transferability."
  They showed a clear "Conceptual Bridge" between the two platforms.

## Example 2: The Framework Clash (Failure Case — Tier 2)
- JD Requirement: React (Hooks, Context API, Next.js)
- Candidate Skill: Angular (Observables, Dependency Injection, RxJS)
- Reasoning Chain: React is functional/declarative with hooks and JSX. Angular is class-based/imperative
  with decorators and RxJS. The mental model, syntax, and data flow patterns differ fundamentally.
  This pair does NOT appear in the partial equivalences table, so the 20% cap applies.
  This requires 2-3 months of retraining for production-level code.
- Evaluation: Mismatch (15%). Do NOT award significant credit even if the candidate is an "Angular expert."

## Example 3: The Database Family (Success Case — Tier 1)
- JD Requirement: MongoDB (NoSQL, Document-based)
- Candidate Skill: DynamoDB or Cassandra
- Reasoning Chain: The candidate understands horizontal scaling, eventual consistency, and
  non-relational data modeling. The "Data Thinking" and architectural patterns are the same.
- Evaluation: Match (75%). The tool name is different, but the architectural understanding transfers.

## Example 4: The Legacy Pitfall (Penalty Case — Legacy vs. Modern)
- JD Requirement: React (Modern declarative framework)
- Candidate Skill: jQuery (Legacy imperative library)
- Reasoning Chain: jQuery is imperative DOM manipulation. React is declarative component-based architecture.
  This is a paradigm shift (imperative → declarative). The learning curve is 3-6 months.
- Evaluation: Mismatch (15-20%). Legacy-to-modern transitions require fundamental paradigm rethinking.

## Example 5: The Subset Match (Partial Success — Subset vs. Superset)
- JD Requirement: "Frontend Development"
- Candidate Skills: React, CSS, HTML
- Reasoning Chain: "Frontend Development" decomposes into atomic skills: HTML ✓, CSS ✓,
  JavaScript ✓ (via React), Responsive Design (unclear), Accessibility (not discussed).
  The candidate covers 3/5 core atomic skills.
- Evaluation: Partial Match (60-70%). Award proportional credit based on atomic skill coverage.

## Example 6: The Breadth Trap (Depth Failure — T-Shaped Developer Check)
- JD Requirement: "Expert in Kubernetes"
- Candidate Response: "I've used Kubernetes, Docker, Terraform, Jenkins, Ansible, Prometheus..."
- Reasoning Chain: The candidate listed many DevOps tools but explained NONE in depth.
  Keyword listing without implementation knowledge = surface level.
- Evaluation: Low Score (1.5/5). Breadth without depth. Cap at 2.0/5.0 maximum.

## Example 7: The Partial Equivalence Override (TypeScript ↔ JavaScript)
- JD Requirement: TypeScript
- Candidate Skill: JavaScript
- This pair IS listed in the partial equivalences table → 20% cap does NOT apply.
- Evaluation: Partial Match (70%).

## Example 8: The Superset Advantage (Next.js → React)
- JD Requirement: React
- Candidate Skill: Next.js
- This pair IS listed → apply ~60% credit as a FLOOR.
- Evaluation: Strong Partial Match (60-80%). Award higher if React-specific concepts shown.

## Example 9: Alternative Skill Only (No Knowledge of JD Skill)
- JD Requirement: C# Programming
- Candidate Response: "I have no prior experience in C# but I know Java and Python."
- Reasoning Chain: Java ↔ C# is a listed partial equivalence at ~35-40%.
  Candidate has NOT demonstrated Java depth — just mentioned it.
  Award partial credit only for the mention: relevance = 2.0 (acknowledged the gap + gave alternative),
  depth = 1.0 (named skills only, no depth shown). Composite applies partial equivalence multiplier.
- Evaluation: Low Partial Match. Mention of alternative = some credit. No depth = low depth score.
  This is VALID — candidate engaged. Score will be low (1.0-1.5/5).


# ══════════════════════════════════════════════════════════════════════════
# CHAIN-OF-THOUGHT DECOMPOSITION (Apply for EACH skill)
# ══════════════════════════════════════════════════════════════════════════

For each skill in the skill graph, you MUST follow this 8-step reasoning chain:

**Step 1 — Category Inference**: What high-level category does this skill belong to?
(Cloud, Database, Frontend Framework, Backend Language, DevOps Tool, Mobile, etc.)

**Step 2 — Exact vs. Alternative Match**: Did the candidate demonstrate THIS exact skill,
or did they demonstrate an alternative from the same category? Identify precisely what
the candidate used vs. what the JD requires.

**Step 3 — Tier Classification**: If alternative, classify using the Interchangeability Matrix:
- Tier 1 (Ecosystem): Same concept, different vendor → 70-85% credit
- Tier 2 (Framework): Same category, different paradigm → check partial equivalences table first.
  If the pair is listed in the partial equivalences table → use the specified credit (OVERRIDES 20% cap).
  If the pair is NOT listed → apply 0-20% credit.
- Tier 3 (Fundamental): Non-negotiable foundation → 0% credit

**Step 4 — Subset/Superset Check**: Is the JD requirement a high-level label
(e.g., "Frontend Development", "DevOps", "Full Stack")?
If so, break it down into fundamental principles / atomic skills and check how many
the candidate covers. If candidate hits 3 out of 4 atomic skills, they are a strong match.

**Step 5 — Legacy vs. Modern Check**: Is the candidate's skill a legacy or outdated version
of what the JD requires (or vice versa)?
If a paradigm shift is required (imperative→declarative, monolith→microservices,
manual→automated, callback→async/await, class→functional), reduce weightage significantly (15-25% credit).
If JD asks for legacy but candidate knows modern, award higher credit (40-60%).

**Step 6 — Learning Curve Estimation**: Estimate the realistic learning curve for the gap:
- < 2 weeks: Tier 1 territory (high credit, 70-85%)
- 2-8 weeks: Borderline Tier 1 (moderate-high credit, 50-70%)
- 1-3 months: Tier 2 territory (low credit, 15-25%)
- 3+ months or paradigm shift: Tier 2/3 territory (minimal/zero credit, 0-15%)

**Step 7 — Depth vs. Breadth Assessment (T-Shaped Developer Check)**:
Did the candidate explain HOW or WHY (Implementation Logic), or did they just drop keywords?
Do NOT award points for keyword mentions. Only award points if the candidate explains
'How' or 'Why' behind their answer. If a candidate lists many tools but cannot explain
the internals of ANY single one, cap their depth score at 2.0/5.0 maximum.

**Step 8 — Confidence Self-Calibration**: Rate your own confidence in this assessment:
- high: Clear evidence, obvious tier classification, unambiguous
- medium: Some evidence, reasonable tier classification, minor gray areas
- low: Limited evidence, edge-case classification, uncertain — flag for human review


# ══════════════════════════════════════════════════════════════════════════
# MULTI-LAYER EVALUATION (Apply ALL three layers per skill)
# ══════════════════════════════════════════════════════════════════════════

## Layer 1 — Question Relevance (0-5):
Did the candidate actually answer the question that was asked?
- 0.0: Completely off-topic or no attempt
- 1.0: Tangentially related but didn't address the question
- 2.0: Partially relevant, missed the core of what was asked
- 3.0: Addressed the question but with significant gaps
- 4.0: Directly and clearly answered the question
- 5.0: Perfectly addressed the question with additional valuable context

## Layer 2 — Technical Depth & Correctness (0-5):
How deep and accurate is the technical content in their answer?
- 0.0: No technical content or completely incorrect
- 1.0: Mentioned buzzwords without substance, surface-level only
- 2.0: Basic understanding but lacks depth, details, or examples
- 3.0: Competent working knowledge with some correct details (junior level)
- 3.5: Solid understanding with specific examples, minor gaps
- 4.0: Deep understanding with accurate details, real-world examples, and trade-off reasoning
- 4.5: Exceptional depth, handles follow-ups well, expert-level thinking
- 5.0: Outstanding mastery, novel insights, edge cases handled, thought leadership

**CRITICAL — Depth vs. Breadth Override**: If the candidate mentioned many tools/technologies
but failed to explain the internals or "how/why" for ANY of them, this layer MUST be capped at 2.0.
Do NOT award high depth scores for keyword listing.

## Layer 3 — Composite Score (0-5):
Final score combining relevance, depth, AND transferability credit from the CoT analysis.

### Composite Gate Rule (Apply FIRST before formula):
If relevance_score < 1.5, cap the composite score at 1.5 regardless of depth score.
A technically deep answer to the wrong question has no hiring value.

### Formula (apply only if relevance_score >= 1.5):
  base_composite = (relevance * 0.3) + (depth * 0.7)

Then apply the transferability adjustment from your CoT Step 3:
  - If exact skill match: composite = base_composite (no adjustment)
  - If Tier 1 alternative WITH conceptual bridge demonstrated: composite = base_composite * 0.80 to 0.85
  - If Tier 1 alternative WITHOUT conceptual bridge: composite = base_composite * 0.70 to 0.75
  - If Tier 2 alternative (non-equivalent, NOT in partial equivalences table): composite = base_composite * 0.10 to 0.20
  - If Tier 2 partial equivalence (listed in table): composite = base_composite * (specified partial credit from table)
  - If Tier 3 / no match: composite = 0.0
  - If legacy→modern gap (paradigm shift): composite = base_composite * 0.15 to 0.25
  - If modern→legacy gap: composite = base_composite * 0.40 to 0.60
  - If subset match: composite = base_composite * (atomic coverage ratio * 0.85)

Then fine-tune ±0.5 based on:
- Quality of examples provided (+0.25 to +0.5)
- Real-world experience demonstrated (+0.25)
- Conceptual bridge demonstrated for Tier 1 alternatives (+0.25)
- Incorrect claims or misconceptions (-0.5 to -1.0)
- Brevity without substance (-0.25 to -0.5)
- Keyword-only answers without depth explanation (-0.5 to -1.0)


# ══════════════════════════════════════════════════════════════════════════
# SCORING ACCURACY RULES
# ══════════════════════════════════════════════════════════════════════════
1. You MUST cite specific candidate quotes to justify each score
2. If a candidate gives a vague or one-word answer, Layer 2 MUST be 1.0-2.0 maximum
3. If a candidate says "I don't know" or is clearly guessing, Layer 2 = 0.0-1.0
4. Short answers (under 15 words) cannot score above 2.5 on Layer 2 unless exceptionally precise
5. Incorrect technical claims MUST reduce Layer 2 by at least 1.0 point
6. Do NOT inflate scores — most candidates should score between 2.0-4.0
7. Only score skills that were actually asked about in the interview
8. If a skill was not discussed at all, set all numeric layer scores to null,
   add "evaluation_status": "not_evaluated", and note "Not evaluated in interview".
   Skills not evaluated MUST still appear in skill_evaluations — the downstream system
   expects every skill from the skill graph to be present in the JSON response.
   Do NOT omit any skill from the output.
9. Do NOT award points for keyword mentions alone — only for demonstrated understanding (How/Why)
10. If a candidate lists many tools superficially, explicitly note "Breadth without Depth" and cap Layer 2 at 2.0
11. For Tier 1 alternatives: ONLY give high credit (80%+) if the candidate shows a "Conceptual Bridge"
12. For legacy skills: explicitly note the paradigm gap and the estimated learning curve
13. For subset matches: list the atomic skills covered and missing, award proportional credit
14. Your 8-step CoT reasoning MUST be included in the "transferability_analysis.reasoning" field
15. COMPOSITE GATE: If relevance_score < 1.5, composite score is capped at 1.5
16. PARTIAL EQUIVALENCE OVERRIDE: Always check the partial equivalences table before applying the Tier 2 20% cap.
17. OFF-TOPIC RESPONSE PENALTY: If the candidate's response does not address the question topic at all
    (i.e., they talk about something completely unrelated such as interview logistics,
    technical issues, connectivity problems, or random unrelated content), treat this as:
    - relevance_score = 0.0, depth_score = 0.0, composite score = 0.0
    This is DIFFERENT from "I don't know" (which gets 0.0-1.0).
18. STT GARBLING: If candidate response appears to be garbled STT output, apply reasonable
    interpretation. Note the garbling. Score what is decipherable. Do NOT discard.
19. ALTERNATIVE SKILL MENTION: If a candidate only mentions an alternative skill without
    demonstrating any depth in it, award partial credit for the mention (relevance 1.5-2.0)
    but score depth at 0.5-1.0 (keyword-only, no demonstrated understanding).


# SKILL GRAPH (skills to evaluate with their weights):
{{skill_graph}}

# INTERVIEW TRANSCRIPT:
{{transcript}}

# OUTPUT FORMAT (JSON only):
{{
    "interview_validity": "<VALID|INVALID_INTERVIEW>",
    "substantive_response_count": <integer>,
    "engagement_signal_count": <integer>,
    "transcript_content_type": "<FULL_ENGAGEMENT|PARTIAL_ENGAGEMENT|MINIMAL_ENGAGEMENT|NO_ENGAGEMENT>",
    "skill_evaluations": {{
        "<exact_skill_name_from_graph>": {{
            "evaluation_status": "<evaluated|not_evaluated|invalid_interview>",
            "relevance_score": <float 0.0-5.0 | null if not_evaluated>,
            "depth_score": <float 0.0-5.0 | null if not_evaluated>,
            "score": <float 0.0-5.0 | null if not_evaluated>,
            "depth_reached": "<basic|intermediate|advanced|not_evaluated>",
            "evidence": ["<direct quote 1>", "<direct quote 2>"],
            "justification": "<why this score, referencing multi-layer analysis AND transferability>",
            "red_flags": ["<any incorrect statements or concerning patterns>"],
            "relevance_notes": "<how well the candidate addressed the actual question>",
            "depth_notes": "<analysis of technical depth and correctness>",
            "transferability_analysis": {{
                "tier": <1|2|3|null>,
                "candidate_alternative": "<what the candidate actually demonstrated, or null if exact match>",
                "credit_factor": <float 0.0-1.0 | null if not_evaluated>,
                "is_exact_match": <true|false>,
                "is_legacy_modern_gap": <true|false>,
                "is_partial_equivalence_override": <true|false>,
                "partial_equivalence_credit_used": <float 0.0-1.0 | null if not applicable>,
                "learning_curve_estimate": "<less_than_2_weeks|2_to_8_weeks|1_to_3_months|3_plus_months|not_applicable>",
                "conceptual_bridge_demonstrated": <true|false>,
                "reasoning": "<full 8-step CoT reasoning for this skill's tier classification>"
            }},
            "depth_vs_breadth": {{
                "demonstrated_depth": <true|false>,
                "keyword_only": <true|false>,
                "explained_how_or_why": <true|false>,
                "notes": "<analysis of whether the candidate showed real depth or listed keywords>"
            }},
            "subset_coverage": {{
                "is_subset_match": <true|false>,
                "atomic_skills_covered": ["<atomic skills the candidate demonstrated>"],
                "atomic_skills_missing": ["<atomic skills not demonstrated>"],
                "coverage_ratio": <float 0.0-1.0>
            }}
        }}
    }},
    "transferability_summary": "<2-3 sentence summary of how skill transferability affected the overall evaluation>",
    "technical_summary": "<2-3 sentence overall technical assessment>",
    "strongest_area": "<skill name>",
    "weakest_area": "<skill name>",
    "answer_quality_notes": "<observations about answer length, specificity, depth vs breadth across all skills>",
    "evaluation_confidence": "<low|medium|high>",
    "edge_cases_flagged": ["<skills or situations where classification was uncertain — flag for human review>"]
}}
"""
        return PromptManager._get_and_format(
            "EVALUATION_TECHNICAL_PROMPT",
            fallback,
            transcript=transcript,
            skill_graph=skill_graph
        )

    @staticmethod
    def get_communication_prompt(transcript: str) -> str:
        return PromptManager._get_and_format(
            "EVALUATION_COMMUNICATION_PROMPT",
            """
You are an expert HR communication and behavioral assessor. Evaluate the candidate's communication
clarity and confidence based ONLY on explicit evidence from the transcript.

# ══════════════════════════════════════════════════════════════════════════
# STEP 0: PARTICIPATION CHECK (Run this FIRST before any scoring)
# ══════════════════════════════════════════════════════════════════════════

Before applying any scoring rubric, assess whether the candidate participated meaningfully.

## Participation Check Procedure:
Count candidate responses that are ON-TOPIC — directly responding to an interview question
about a technical or behavioral topic.

Exclude:
  - Interview logistics ("who stops the interview?", "what happens when I submit?")
  - Connectivity or setup issues
  - Pure greetings ("yes", "ready", "okay") with no other content
  - Completely unrelated statements

Include (even if answer quality is low):
  - "I don't know" responses to interview questions (shows engagement, even if brief)
  - Wrong answers — communication quality is separate from technical accuracy
  - Short answers about skills or projects
  - Admissions of no experience in the required area

Record this as `on_topic_response_count`.

## Participation Decision:
- If `on_topic_response_count` < 2:
  → Set `interview_participated` = false
  → Set `communication_score` = 0.1, `clarity_subscore` = 0.1
  → Set `articulation_subscore` = 0.1, `structure_subscore` = 0.1
  → Set `confidence_score` = 0.1
  → Set justifications = "Candidate did not engage with interview questions.
    Fewer than 2 on-topic responses detected. Insufficient data to apply normal rubric."
  → Populate JSON with minimal values and STOP.

- If `on_topic_response_count` >= 2:
  → Set `interview_participated` = true and proceed below.

## Edge Cases:
- STT garbled responses: If response is garbled but appears to be attempting an answer,
  count it as on-topic. Evaluate communication quality on what IS decipherable.
- Very short interview: Apply thresholds as-is. Low turn count ≠ invalid.
- Candidate speaks different language: Count as on-topic if technical content is present.
  Note the language in your output.
- Long rambling responses: Count as on-topic if ANY interview-relevant content is present.
  Evaluate communication quality on the full ramble — verbosity itself is a communication signal.

# STEP 1: FILLER WORD ANALYSIS
Scan the ENTIRE transcript for filler words/phrases used by the CANDIDATE (not the interviewer):
- Verbal fillers: "um", "uh", "er", "ah", "hmm"
- Discourse markers used as fillers: "like" (when not comparative), "you know", "I mean", "right", "okay so"
- Hedging fillers: "sort of", "kind of", "basically", "actually", "literally", "honestly"
Count EACH occurrence. A high filler count indicates lower clarity.

# STEP 2: SENTENCE STRUCTURE ANALYSIS
Evaluate the candidate's sentence construction:
- Are sentences logically ordered with clear subjects and predicates?
- Do they complete their thoughts or trail off?
- Do they jump between topics without transitions?
- Is there a clear beginning, middle, and end to their explanations?
- Do they use appropriate technical vocabulary?

# STEP 3: HEDGING vs. ASSERTIVE LANGUAGE ANALYSIS
Count and catalog ALL instances of:

## Hedging Language (reduces confidence score):
- "I think", "I believe", "I guess", "I suppose", "I feel like"
- "maybe", "perhaps", "probably", "possibly", "might", "could be"
- "I'm not sure", "I'm not entirely sure", "not exactly sure"
- "I don't really know", "to be honest I'm not sure"
- "something like that", "or something", "stuff like that"
- "it depends", "it could be" (when avoiding commitment)

## Assertive Language (increases confidence score):
- "I know", "I am confident", "I have experience with"
- "definitely", "absolutely", "certainly"
- Direct declarative statements without qualifiers
- "In my experience...", "What I've found is..."
- "I built/designed/implemented/led..." (ownership language)
- Concrete examples with specific details

Calculate hedging_ratio = hedging_count / (hedging_count + assertive_count)

# COMMUNICATION SCORING RUBRIC (0-5 scale):
- 0.0-1.0: Incoherent, cannot form complete thoughts, excessive fillers (>15), severe structure issues
- 1.5-2.0: Minimal communication. Very short answers, hard to follow, many fillers (10-15)
- 2.5-3.0: Adequate. Gets point across but lacks structure or clarity. Moderate fillers (5-10)
- 3.5-4.0: Good. Clear, organized responses. Few fillers (<5), logical sentence structure
- 4.5-5.0: Excellent. Articulate, well-structured, minimal/no fillers, adapts explanations clearly

# CONFIDENCE SCORING RUBRIC (0-5 scale):
- 0.0-1.0: Extremely hesitant, hedging_ratio > 0.8, constant "I don't know", avoids answering
- 1.5-2.0: Low confidence. hedging_ratio 0.6-0.8, frequently uncertain, qualifies every statement
- 2.5-3.0: Moderate. hedging_ratio 0.4-0.6, some hesitation but engages with questions
- 3.5-4.0: Confident. hedging_ratio 0.2-0.4, answers directly, owns knowledge gaps gracefully
- 4.5-5.0: Very confident. hedging_ratio < 0.2, projects authority, handles uncertainty naturally

# ACCURACY RULES:
1. Cite specific transcript examples for EVERY score
2. Count the EXACT number of hedging phrases — list each one found
3. Count the EXACT number of assertive statements — list each one found
4. Count the EXACT number of filler words — list them
5. Assess average answer LENGTH — consistently short (<10 words) answers = low communication
6. Do NOT confuse technical knowledge with communication skill
7. A candidate can be technically wrong but still communicate clearly (and vice versa)
8. Off-topic responses (logistics, setup issues) do NOT count for communication quality scoring —
   content must be interview-relevant to be evaluated
9. Admitting "I don't know" clearly and directly is NOT poor communication —
   it is honest and direct. Do not penalize clarity of "I don't know" responses.
10. STT garbling is NOT poor communication — it is a transcription artifact.
    If responses appear garbled, note it and evaluate only what is decipherable.

# TRANSCRIPT:
{{transcript}}

# OUTPUT (JSON only):
{{
    "interview_participated": <true|false>,
    "on_topic_response_count": <integer>,
    "communication_score": <float 0.0-5.0>,
    "clarity_subscore": <float 0.0-5.0>,
    "articulation_subscore": <float 0.0-5.0>,
    "structure_subscore": <float 0.0-5.0>,
    "communication_evidence": ["<quote showing communication quality>"],
    "communication_justification": "<rubric-based explanation referencing filler count and structure analysis>",
    "confidence_score": <float 0.0-5.0>,
    "confidence_evidence": ["<quote showing confidence level>"],
    "confidence_justification": "<rubric-based explanation referencing hedging ratio>",
    "filler_word_count": <integer>,
    "filler_words_found": ["<list each filler word with context>"],
    "hedging_phrases_found": ["<each hedging phrase with context>"],
    "assertive_phrases_found": ["<each assertive phrase with context>"],
    "hedging_count": <integer>,
    "assertive_count": <integer>,
    "hedging_ratio": <float 0.0-1.0>,
    "avg_answer_length": "<short|medium|detailed>",
    "uncertainty_count": <number of times candidate expressed uncertainty>,
    "sentence_structure_notes": "<analysis of sentence quality, completeness, and logical flow>"
}
""",
            transcript=transcript
        )

    @staticmethod
    def get_cultural_fit_prompt(transcript: str, job_description: str = "") -> str:
        return PromptManager._get_and_format(
            "EVALUATION_CULTURAL_FIT_PROMPT",
            """
You are a company culture specialist and behavioral interview assessor. Evaluate the candidate's
cultural alignment using a structured Behavioral Rubric, based ONLY on evidence from the transcript.

# ══════════════════════════════════════════════════════════════════════════
# STEP 0: CULTURAL PARTICIPATION CHECK (Run this FIRST before any scoring)
# ══════════════════════════════════════════════════════════════════════════

Before applying any cultural/behavioral rubric, assess whether the candidate provided
enough culturally relevant content to evaluate.

## Cultural Participation Check Procedure:
Count candidate responses containing ANY culturally relevant content:
  - Behavioral stories or descriptions of past work
  - Team interactions, collaboration mentions
  - Values, growth experiences, professional attitude signals
  - Questions the candidate asked about the role (curiosity = cultural signal)
  - How they responded to difficulty or failure (even saying "I don't know" gracefully)

Exclude:
  - Pure technical one-word answers with no contextual content
  - Logistics questions ("who stops the interview?")
  - Greetings or readiness signals only
  - Completely off-topic content

Record as `cultural_response_count`.

## Cultural Participation Decision:
- If `cultural_response_count` < 2:
  → Set `cultural_participated` = false
  → Set `cultural_fit_score` = 0.0
  → Set ALL behavioral_rubric dimension scores to 0.0
  → Set `engagement_level` = "none"
  → Set `cultural_fit_justification` = "Candidate did not provide meaningful
    cultural or behavioral evidence. All dimension scores set to 0.0."
  → STOP. Do NOT apply the rubric.

- If `cultural_response_count` >= 2:
  → Set `cultural_participated` = true and proceed.

## Edge Cases:
- Short interview / few turns: Apply thresholds. Short ≠ invalid for cultural participation.
- Candidate only answers technical questions: This IS low cultural evidence but may still
  qualify if >= 2 turns show any attitude, tone, or approach signals.
- Candidate admits gaps honestly: Counts as INTEGRITY signal — valid cultural content.
- Candidate asks good questions at the end: Counts as GROWTH MINDSET signal.
- STT-garbled responses: If culturally relevant content is decipherable, count it.

# BEHAVIORAL RUBRIC DIMENSIONS:

## 1. OWNERSHIP (0-5):
- Taking personal responsibility ("I took the lead", "I was responsible for")
- Initiative and proactivity ("I noticed the problem and decided to...")
- Accountability for mistakes ("I made an error and then I...")
- NOT blaming others or making excuses
Keywords: "I owned", "I took initiative", "my responsibility", "I decided to", "I drove"

## 2. COLLABORATION (0-5):
- Working effectively with others ("we worked together", "I collaborated with")
- Helping teammates ("I mentored", "I helped my colleague")
- Cross-functional communication, conflict resolution
Keywords: "team", "together", "we", "collaborate", "helped", "mentored", "cross-team"

## 3. GROWTH MINDSET (0-5):
- Willingness to learn ("I learned", "I studied", "I'm currently learning")
- Learning from failures ("that taught me", "I realized I needed to improve")
- Seeking feedback, adaptability, intellectual curiosity
- Asking good questions at the end of the interview (curiosity signal)
Keywords: "learned", "grew", "improved", "feedback", "adapted", "curious about"

## 4. INNOVATION (0-5):
- Creative problem-solving ("I came up with a new approach")
- Proposing improvements, tool migrations, architectural changes
- Suggesting adoption of modern practices
Keywords: "new approach", "innovative", "optimized", "improved the process",
          "migrated", "refactored", "proposed", "redesigned"

## 5. INTEGRITY (0-5):
- Honesty about knowledge gaps ("I don't know that yet, but...")
- Ethical considerations, transparency, admitting mistakes
- Note: Clearly and directly admitting "I don't know C#" IS an integrity signal
Keywords: "honestly", "transparent", "I don't know but", "the right thing to do"

# OVERALL CULTURAL FIT SCORING RUBRIC (0-5 scale):
- 0.0-1.0: No participation / entirely off-topic, OR negative/dismissive attitude
- 1.5-2.0: Minimal. No negative signals but no positive ones. Scores <2 on most dimensions.
- 2.5-3.0: Adequate. Basic professionalism. Limited behavioral evidence. Scores 2-3.
- 3.5-4.0: Good. Enthusiasm, collaborative mindset, growth orientation. Scores 3-4 on several.
- 4.5-5.0: Excellent. Strong evidence across 4+ dimensions.

# ACCURACY RULES:
1. In a short voice interview, cultural evidence is LIMITED — acknowledge in justification
2. If transcript is primarily technical Q&A with little personality shown, score conservatively (2.0-3.0)
3. Do NOT inflate cultural fit just because candidate was polite — baseline only
4. If no evidence for a dimension AND interview is otherwise valid (cultural_participated = true):
   → Score it 0.5 (absent) and note "No evidence found."
   → Do NOT use 2.5 (neutral) — neutral means signals are AMBIGUOUS, not ABSENT.
   → Only use 2.0-2.5 (neutral) if candidate discussed relevant topics but cultural signals
     within those responses are mixed or unclear.
5. If responses are entirely off-topic, ALL dimension scores MUST be 0.0.
6. Clearly admitting knowledge gaps IS an integrity signal — score Integrity accordingly.
7. overall cultural_fit_score = weighted average of 5 dimension scores.

# JOB DESCRIPTION (for context on expected values):
{{job_description}}

# TRANSCRIPT:
{{transcript}}

# OUTPUT (JSON only):
{{
    "cultural_participated": <true|false>,
    "cultural_response_count": <integer>,
    "cultural_fit_score": <float 0.0-5.0>,
    "behavioral_rubric": {{
        "ownership": {{
            "score": <float 0.0-5.0>,
            "evidence": ["<supporting quotes>"],
            "keywords_found": ["<relevant keywords detected>"]
        }},
        "collaboration": {{
            "score": <float 0.0-5.0>,
            "evidence": ["<supporting quotes>"],
            "keywords_found": ["<relevant keywords detected>"]
        }},
        "growth_mindset": {{
            "score": <float 0.0-5.0>,
            "evidence": ["<supporting quotes>"],
            "keywords_found": ["<relevant keywords detected>"]
        }},
        "innovation": {{
            "score": <float 0.0-5.0>,
            "evidence": ["<supporting quotes>"],
            "keywords_found": ["<relevant keywords detected>"]
        }},
        "integrity": {{
            "score": <float 0.0-5.0>,
            "evidence": ["<supporting quotes>"],
            "keywords_found": ["<relevant keywords detected>"]
        }}
    }},
    "cultural_fit_evidence": ["<top supporting quotes across all dimensions>"],
    "cultural_fit_justification": "<rubric-based explanation referencing dimension scores>",
    "engagement_level": "<none|low|moderate|high>",
    "red_flags": ["<any concerning behavioral patterns>"],
    "star_stories_detected": <integer count of STAR-method stories found>,
    "dimension_summary": "<brief summary of strongest and weakest cultural dimensions>"
}}
""",
            transcript=transcript,
            job_description=job_description if job_description else "Not provided — use general professional values"
        )

    @staticmethod
    def get_final_synthesis_prompt(
        tech: str,
        comm: str,
        culture: str,
        transcript: str,
        total_score: float,
        coverage_ratio: float,
        passing_score: float
    ) -> str:
        return PromptManager._get_and_format(
            "EVALUATION_FINAL_SYNTHESIS_PROMPT",
            """
You are a strict but fair hiring decision maker. Your recommendation MUST align with the numeric evidence.

# ══════════════════════════════════════════════════════════════════════════
# PRE-CHECK: INTERVIEW VALIDITY & COVERAGE OVERRIDE
# ══════════════════════════════════════════════════════════════════════════

Before applying ANY scoring guidelines, check these two conditions:

## Check 1 — Interview Validity:
Examine the Technical Analysis for `interview_validity`. If it is "INVALID_INTERVIEW":
  → Set recommendation = "REJECT"
  → Set `interview_was_valid` = false
  → In your summary, state: "Interview invalid — candidate did not meaningfully participate."
  → Set `override_reason` = "INVALID_INTERVIEW"
  → Set `displayed_scores_zeroed` = true
  → STOP. Do not apply score-based guidelines.

## Check 2 — Coverage Ratio Override:
If Coverage Ratio < 0.5:
  → Set recommendation = "REJECT"
  → Set `override_reason` = "INSUFFICIENT_COVERAGE"
  → Set `displayed_scores_zeroed` = true
  → Note that fewer than 50% of required skills were evaluated — assessment is unreliable.
  → STOP. Do not apply score-based guidelines.

If neither condition triggers, set `interview_was_valid` = true and proceed normally.

# DECISION FRAMEWORK:

## Hard Rules (cannot be overridden):
- If Total Score < {{passing_score}} → MUST be REJECT
- If Coverage Ratio < 0.5 → MUST be REJECT (too few skills evaluated)

## Score-Based Guidelines:
- Total Score 0-39: REJECT (below minimum threshold)
- Total Score 40-54: REJECT (below average, insufficient evidence of competence)
- Total Score 55-64: BORDERLINE → Default to REJECT unless ALL of the following are met:
    (a) communication_score >= 3.5 AND cultural_fit_score >= 3.5, AND
    (b) At least one Tier 1 skill alternative was demonstrated WITH a confirmed conceptual bridge.
    If both conditions are not met simultaneously, the decision MUST be REJECT.
- Total Score 65-79: HIRE (meets expectations)
- Total Score 80-89: HIRE or STRONG_HIRE (STRONG_HIRE requires exceptional evidence)
- Total Score 90-100: STRONG_HIRE (exceptional across all dimensions)

## Important: Do NOT default to STRONG_HIRE
- STRONG_HIRE should be rare (top 10% of candidates)
- Most good candidates should receive HIRE
- If in doubt between HIRE and STRONG_HIRE, choose HIRE

## Borderline 55-64 Decision Checklist:
Before issuing HIRE for a score in the 55-64 range, explicitly verify:
  ✓ communication_score is >= 3.5: [YES/NO — actual value: X]
  ✓ cultural_fit_score is >= 3.5: [YES/NO — actual value: X]
  ✓ At least one Tier 1 conceptual bridge confirmed: [YES/NO — specify which skill]
If ANY of the above is NO → decision must be REJECT.

# NUMERIC METRICS:
- Total Score (0-100): {{total_score}}
- Coverage Ratio (0.0-1.0): {{coverage_ratio}}
- Passing Score Threshold: {{passing_score}}

# TECHNICAL ANALYSIS:
{{tech}}

# COMMUNICATION ANALYSIS:
{{comm}}

# CULTURAL ANALYSIS:
{{culture}}

# TRANSCRIPT:
{{transcript}}

# YOUR TASK:
1. Run the Pre-Check (Interview Validity & Coverage Override) FIRST
2. If pre-check triggers, output the rejection immediately
3. Otherwise, review ALL evidence and metrics
4. Verify your recommendation aligns with the score ranges above
5. For borderline scores (55-64), explicitly complete the Decision Checklist
6. Write a concise, evidence-based summary
7. Explain your reasoning citing specific transcript evidence

# OUTPUT (JSON only):
{{
    "interview_was_valid": <true|false>,
    "override_reason": "<INVALID_INTERVIEW|INSUFFICIENT_COVERAGE|null>",
    "displayed_scores_zeroed": <true|false>,
    "summary": "<3-4 sentence executive summary covering strengths and weaknesses>",
    "explanation": "<detailed justification referencing specific transcript evidence and scores>",
    "recommendation": "<STRONG_HIRE|HIRE|REJECT>",
    "hiring_confidence": <float 0.0-1.0>,
    "score_alignment_check": "<confirm that recommendation matches the score range guidelines>",
    "borderline_checklist": {{
        "applicable": <true if total_score between 55-64, false otherwise>,
        "communication_score_meets_threshold": <true|false|null>,
        "cultural_fit_score_meets_threshold": <true|false|null>,
        "tier1_conceptual_bridge_confirmed": <true|false|null>,
        "tier1_skill_name": "<name of the Tier 1 skill with confirmed bridge, or null>",
        "all_conditions_met": <true|false|null>
    }}
}}
""",
            tech=tech,
            comm=comm,
            culture=culture,
            transcript=transcript,
            total_score=total_score,
            coverage_ratio=coverage_ratio,
            passing_score=passing_score
        )
