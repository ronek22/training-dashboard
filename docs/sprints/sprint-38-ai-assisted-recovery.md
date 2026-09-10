# Sprint 38: AI-Assisted Recovery

## Status

Foundation implemented on 2026-09-07. The Recovery page, persistent issues, optional AI intake conversations, structured symptom checks, care guidance, check-ins, and opt-in coaching summaries are available. Routine generation/save/versioning is implemented behind the clinical-review release gate. Exercise recommendations remain unavailable until a qualified review of screening and library entries is recorded; the full exercise-release acceptance criteria are therefore not complete.

## Implemented Behavior

- `/recovery` is available in Training navigation and linked from Trends → Recovery.
- Issues support active/archived state and complete app-data deletion. Private notes work without AI sharing; opting into AI sends that issue's history and recent check-ins plus a limited training-context payload.
- The assistant receives persisted intake, recent training/readiness, saved plan, and modality restrictions. It returns a validated summary, known follow-up question IDs, a concern level, optional reviewed exercise selections, and a sparse proposed intake grounded in athlete-message quotes. Proposals fill the review form but never silently change confirmed intake.
- Screening and routine validation run on the backend. New symptom messages and all check-ins require a fresh confirmed check and pause existing routines. Urgent concerns from chat or worsening check-ins stay visible; a later low score does not clear them.
- Each asynchronous request is bound to the issue revision. Retry replaces the pending request; changed, archived, or deleted issues reject old results. Replies persist on the backend even if the page has been closed.
- The helper keeps only request identifiers/status in its jobs. Symptom content and raw model errors are excluded from job responses/log messages. Temporary CLI outputs use the existing ephemeral-run pattern. Deletion removes app-side history; it cannot revoke data already sent to the configured model provider.
- Sharing confirmed symptom summaries into Coach/planning context is separately opt-in and excludes conversation text. The training-restriction handoff opens the existing editor with saved restrictions; it makes no automatic changes.
- The UI includes loading, retry, AI-unavailable, screening, routine-unavailable, and archived states. Unsaved intake changes block routine actions until confirmed; chat preserves those drafts and can continue without completing the form.

### Live chat fix (2026-09-08)

- The installed helper process had been started before Recovery existed and returned HTTP 404 for `/recovery-chat`. Restarted it with the new endpoint and successfully generated/persisted a real reply to the athlete's previously submitted message.
- Definitively rejected helper starts now mark the backend request failed and show an actionable error inside the conversation. Pending requests older than 17 minutes expire, so an orphaned request cannot stay pending forever. Ambiguous network failures preserve potentially running requests.
- Open conversations poll persisted pending requests after reload, preserving unsaved intake edits. Replies already in progress do not require a fresh sharing choice merely to appear.
- Separate Send to assistant and Save private note buttons explain that private notes do not receive AI replies. Sharing remains explicit; filling the symptom form is no longer a prerequisite to chatting.
- The helper health response advertises Recovery support; starting against an outdated installed helper reports the required restart instead of silently declaring it ready.
- Regression coverage includes the old-helper 404, uncertain transport failures, success polling, navigation away, and orphaned-request expiry.

### Conversation-to-summary workflow (2026-09-08)

- Each chat reply can prepare typed symptom fields with exact supporting quotes from athlete messages. Missing answers remain unknown; guesses about diagnosis and unsupported negative warning signs must not be inferred. Every proposed field requires source evidence, and invalid types or future onset dates are rejected.
- The proposal is persisted against the issue revision and survives reload. Changed symptoms invalidate its availability for confirmation; previous proposed facts remain available to the assistant for continuity.
- The review form automatically fills from the latest proposal and preserves athlete corrections during asynchronous replies. A highlighted summary shows proposed values and their source quotes; the athlete can edit any field before pressing **Confirm summary & see next step**.
- Confirmation uses the existing revision-checked intake endpoint and clears the pending proposal. New confirmed facts drive the next-action card: review missing details, seek indicated care, request an eligible routine, or log a follow-up. Urgent/emergency care guidance takes priority over summary review.
- Existing conversations without proposals have a **Prepare summary from conversation** action. No retyping of known symptoms is required, and partial summaries can be confirmed while unanswered screening remains unknown.
- Exercise release remains gated by the documented clinical-review dependency; summary confirmation does not manufacture clearance or unlock unreviewed routines.

### Confirmation outcome fix (2026-09-08)

- Confirmation now displays a persistent **Summary saved** result directly below the form; it no longer scrolls away as the only feedback. The unchanged confirmed form cannot be redundantly submitted.
- Confirmed issues with assessment recommendations lead to training options and follow-up tracking even if an onset date is unknown. Missing information no longer traps the athlete in a review/confirm loop.
- Partial summaries without an assessment recommendation point to an explicit unanswered-question list, while urgent/emergency guidance retains priority. The saved state and next step survive reload.
- Regression tests cover both the assessment-with-missing-date case and the partial-summary case; frontend production build passes.

## Release Dependency

See [Recovery library review](../recovery-library-review.md). No clinical approval or exercise eligibility has been fabricated. The reviewed library is deliberately empty; there is no fallback routine. The current prescription contract supports repetitions and sets; timed stretching prescriptions and condition-specific rehabilitation remain future reviewed extensions.

## Verification Performed

- Targeted backend/recovery-helper/existing-helper tests pass, including stale requests, screening bypass attempts, deletion, private notes, explicit sharing, prescription bounds, library withdrawal, and worsening follow-up.
- Frontend production build passes.
- Browser checks use a temporary database and synthetic data: issue creation, private notes, confirmed screening, routine release gate, worsening check-in, reload persistence, a deterministic AI test reply, opt-in sharing, and the restriction-editor handoff. The test reply verifies the complete helper/API/UI path; it is not a real-model clinical evaluation.
- The broader 58-test app smoke suite has three pre-existing failures: activity stats with dated fixtures, strength-context source label expectations, and a zone-goal fixture. All three reproduce in an isolated baseline with Recovery registration/schema changes removed and existing user edits preserved.

## Running The Feature

The backend creates the new SQLite tables at startup. Restart an already-running local Codex planning helper to load its new `/recovery-chat` endpoint; the normal app continues using the existing helper on port 8765. The helper's recovery backend URL defaults to `http://localhost:8000`; `TRAINING_DASHBOARD_API_URL` can point a separate test deployment at its own backend. No new model credentials are introduced.

## Objective

Give athletes a dedicated place to discuss soreness or symptoms, keep a history of each issue, and follow an appropriate recovery routine with feedback. Connect recovery to actual training context and existing modality restrictions.

The product should offer recovery support without claiming to diagnose injuries, cure symptoms, or clear an athlete to return to sport.

## Athlete Experience

1. Open **Recovery** and start an issue, for example “My calves feel sore after yesterday’s run.” Existing issues show the latest check-in and next action.
2. Chat naturally. The assistant asks only for missing information: location and side, onset and mechanism, severity, change over time, effect on normal movement, relevant warning signs, and any clinician instructions. Training history can supply context but cannot answer symptom questions for the athlete.
3. Review the captured symptom summary and correct it. Missing information stays unknown; the app must not infer that unmentioned warning signs are absent.
4. Receive one of three next steps: answer more questions, seek professional assessment, or review an eligible general soreness/mobility routine. Screening is not a diagnosis or a guarantee of safety.
5. Review a short routine with exercise instructions, purpose, duration or repetitions, frequency, equipment, and specific stop conditions. Save it explicitly.
6. Log completion and symptoms before, after, and at the next check-in. Worsening symptoms pause suggestions and trigger reassessment; completion alone does not justify progression.
7. Review suggested training restrictions or plan changes separately before applying them.

## First-Version Scope

- Dedicated Recovery page with persistent issue-specific conversations, structured intake, saved routines, and check-in history.
- Narrow initial routine coverage for general post-training soreness and gentle mobility, with eligibility and exclusions defined for each reviewed library entry.
- AI asks questions, summarizes athlete reports, selects eligible library entries, and explains the proposed routine in context.
- Exercise instructions and dosage bounds come from a versioned, professionally reviewed library with source references. Existing strength exercise metadata may support display, but does not establish rehabilitation suitability.
- Known injuries, persistent or worsening symptoms, recent surgery, and unclear presentations follow a professional-assessment path in the initial release. Athlete-supplied clinician guidance can be recorded with its provenance; AI must not silently replace it.
- Reuse recent training, readiness, workout feedback, and explicit restrictions as context. Favor a concise active-issue summary over sharing complete symptom transcripts with every coaching request.
- Explicit loading, unavailable-helper, failed-generation, and retry states. Preserve the conversation when generation fails; do not substitute a generic routine.
- Allow issue deletion with linked messages, routines, and check-ins removed. Explain what symptom data is saved and sent to the configured AI before first use; exclude transcript contents from routine logs.

## Safety Behavior

Use structured screening and server-side validation in addition to model instructions. An AI response must never override an escalation state or an unresolved screening answer. Keyword matching alone is inadequate for negation, context, or newly reported symptoms.

Examples requiring escalation include substantial or worsening pain/swelling and inability to bear weight after injury. Emergency presentations include deformity or a numb/cold injured limb, and back pain with new bladder/bowel changes or loss of sensation around the genitals. These examples are not an exhaustive screening protocol; final questions, urgency, and exercise eligibility require qualified clinical review before release. Emergency wording must use the athlete's locale rather than assuming UK contact numbers.

When escalation or unresolved screening applies, withhold exercise generation and show the appropriate next step. Reassess when the athlete reports new symptoms. Show why routine suggestions are withheld without labeling the athlete's condition.

Reference guidance consulted on 2026-09-07:

- [NHS: Sprains and strains](https://www.nhs.uk/conditions/sprains-and-strains/) — injury escalation signs and initial care context.
- [NHS: Back pain](https://www.nhs.uk/conditions/back-pain/) — urgent and emergency symptom guidance.

These references inform the proposal; they do not validate a complete automated screening system or exercise library.

## Implementation Approach

### Data and API

Introduce dedicated recovery models, repositories, services, and routes following the backend's existing domain structure. Proposed entities:

- `recovery_issues`: athlete-entered concern, structured intake, screening state, relevant restrictions, timestamps, and active/archived status.
- `recovery_messages`: issue-linked athlete/assistant messages.
- `recovery_routines`: versioned exercise IDs and prescriptions, source intake revision, review/save state, and generation provenance.
- `recovery_checkins`: issue/routine linkage, completion, symptom reports, function changes, and timestamps.

Keep screening state separate from issue lifecycle: archiving an issue is not evidence of clinical recovery. Validate enum values, lengths, dosage bounds, issue ownership/linkage, and exercise IDs on the server. A routine generated against an older intake revision cannot be saved without reassessment.

### AI and Frontend

Reuse the local helper's asynchronous job pattern and the coach conversation UI patterns, with a recovery-specific structured output contract. Fetch persisted intake/history on the server, maintain symptom facts independently of truncated chat history, and treat all free text as untrusted data. The model proposes actions; deterministic application code validates and persists explicitly accepted changes.

Add a `/recovery` route and navigation entry. The main page combines active issues, the selected conversation, routine cards, and a simple symptom timeline. Keep Trends → Recovery focused on sleep/HRV/RHR and link to the new module with clear wording where useful.

### Planning Integration

Start with reviewable proposals using the existing modality-restriction workflow. Preserve existing clinician or athlete restrictions. Applying a restriction or changing a plan must be an explicit athlete action; a chat reply or routine save cannot mutate either implicitly. Preserve existing protected-day and completed-session rules.

## Delivery Slices

1. Persistent issues, symptom intake, conversations, screening/escalation UI, and professional-care path.
2. Reviewed general soreness/mobility library, validated AI routine selection, explicit save, and check-ins.
3. Compact coaching context and reviewable restriction/plan handoff.

Clinical review of screening and the initial exercise library is a release dependency for slice 2. Until that exists, ship intake/history and care navigation without presenting generated exercises as validated recovery advice.

## Acceptance Criteria

- An athlete can resume an issue after reload without losing confirmed symptom facts.
- Unanswered screening questions, new warning signs, and conflicting answers prevent routine generation; model output cannot bypass this behavior.
- No routine is generated for an unsupported presentation or an unreviewed exercise entry.
- Invalid exercise IDs, out-of-bounds dosage, malformed output, and stale intake revisions are rejected.
- Saved routines show instructions, dose, sources, and stop conditions; check-ins remain linked to the routine version performed.
- Worsening follow-up symptoms pause existing routine guidance pending reassessment.
- Helper errors leave the athlete's messages intact and offer an actionable retry state.
- Deleting an issue removes its associated symptom data, including stored generation artifacts; logs do not retain transcript contents.
- Proposed restrictions and plan changes remain unapplied until explicitly accepted.
- Backend scenario tests cover screening bypass attempts, unknown/negated symptoms, stale jobs, invalid prescriptions, persistence, and deletion. Verify the frontend build and the complete intake-to-check-in flow, including care-escalation and AI-unavailable states.

## Out Of Scope

- Automated diagnosis or injury probability scores.
- Condition-specific rehabilitation, medication advice, or autonomous return-to-sport clearance.
- Automatic training-plan changes or automatic progression based solely on lower pain scores.
- Generated exercise demonstrations presented as clinically verified technique.
