Final Read-Only Technical Review

> Historical report: this review predates both its documented remediation and
> the approved 2 November 2026 multi-curriculum expansion. Its scope and
> readiness statements describe the reviewed baseline. Current status and
> contracts are maintained in `IMPLEMENTATION_PLAN.md`, `DECISIONS.md`,
> `API_CONTRACT.md`, and `DATABASE_SCHEMA.md`.
Recommendation: not ready for full manual end-to-end testing yet.

All 16 use cases have implementation paths, and the overall architecture is coherent. However, one Critical AI-provider incompatibility will likely prevent question generation entirely, and several High findings can cause incorrect approval, incorrect published marks, lost student answers, or post-submission answer mutation.

Environment preparation can begin, but the Critical and High findings should be corrected before an acceptance-testing cycle.

No files were modified. No dependencies, builds, tests, migrations, servers, provider calls, or deployments were executed.
Critical
C-01 — OpenAI strict structured-output schema is incompatible
The provider submits a raw Pydantic JSON schema with strict: true:
- [provider.py (line 56)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\provider.py:56)
- [contracts.py (line 77)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\contracts.py:77)
- [prompts.py (line 52)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\prompts.py:52)
Several model fields have defaults and therefore are not included as required fields, while generated object schemas do not consistently declare additionalProperties: false.

Current official OpenAI Structured Outputs documentation requires every field to be required and every object to set additionalProperties: false when strict mode is used. An unsupported strict schema receives an API error.

Expected impact: question generation and regeneration are likely to fail with an OpenAI HTTP 400, blocking UC-06 and part of UC-07.
High
H-01 — Generation counts have no server-side maximum
- [contracts.py (line 32)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\contracts.py:32)
- [service.py (line 162)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\service.py:162)
- [generation page (line 7)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\generate\\page.tsx:7)
Per-type counts require only >= 0. An authenticated teacher can request an extremely large batch, causing excessive memory, CPU, prompt size, and provider cost. Enforce per-type and aggregate limits on the backend.
H-02 — The UI can approve content different from the visible edits
- [batch review page (line 10)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\batches[id]\\page.tsx:10)
- [batch review page (line 19)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\batches[id]\\page.tsx:19)
- [batch review page (line 37)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\batches[id]\\page.tsx:37)
- [batch review page (line 47)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\batches[id]\\page.tsx:47)
- [router.py (line 188)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\router.py:188)
Edits live locally until “Save edits” succeeds. The teacher can change a question and click “Approve” without saving; approval then applies to the old server version while the edited version remains visible. A failed save produces the same risk.

This violates the teacher-control expectation in UC-07.
H-03 — Failed evaluation autosaves can publish stale server marks
- [evaluation page (line 27)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\evaluations[id]\\page.tsx:27)
- [evaluation page (line 31)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\evaluations[id]\\page.tsx:31)
- [evaluation page (line 38)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\evaluations[id]\\page.tsx:38)
- [evaluation page (line 50)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\evaluations[id]\\page.tsx:50)
- [evaluation page (line 74)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\evaluations[id]\\page.tsx:74)
- [teacher_api.py (line 133)](D:\\Projects\\LotusSmartStudy\\backend\\app\\teacher_api.py:133)
The frontend keeps locally edited marks after a save failure. It can still show the attempt as complete and enable publication. The backend publishes the previously persisted evaluations, so the published total can differ from the teacher’s confirmation dialog.

This affects UC-14 and UC-15.
H-04 — Recent typed answers can be lost during navigation or unload
- [attempt page (line 47)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\student\\attempts[id]\\page.tsx:47)
- [attempt page (line 76)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\student\\attempts[id]\\page.tsx:76)
- [attempt page (line 79)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\student\\attempts[id]\\page.tsx:79)
Unmount cleanup cancels the debounce timer without flushing the pending text. Reload, browser back, tab close, or navigation outside the test within the debounce interval loses the latest edit despite displaying “Saving…”.

This fails part of UC-10’s persistence acceptance criterion.
H-05 — Image mutations can commit after submission
- [student_api.py (line 156)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:156)
- [student_api.py (line 182)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:182)
- [student_api.py (line 192)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:192)
- [student_api.py (line 216)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:216)
- [student_api.py (line 249)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:249)
- [student_api.py (line 266)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:266)
Submission locks the attempt row, but upload creation, completion, reordering, and deletion do not use that lock. An image operation can verify in_progress, submission can commit, and the image operation can then commit afterward.

This can mutate the teacher-visible answer after submission, violating UC-12 and UC-13 immutability.
H-06 — Configured pixel limits are checked after image decoding
- [storage.py (line 71)](D:\\Projects\\LotusSmartStudy\\backend\\app\\storage.py:71)
- [storage.py (line 76)](D:\\Projects\\LotusSmartStudy\\backend\\app\\storage.py:76)
- [storage.py (line 83)](D:\\Projects\\LotusSmartStudy\\backend\\app\\storage.py:83)
The image is fully loaded before width × height is compared with the configured limit. A small compressed decompression-bomb image can consume substantial memory before rejection, potentially exhausting an API worker.
Medium
M-01 — Concurrent image grants can exceed limits or collide on page order
- [student_api.py (line 202)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:202)
- [student_api.py (line 207)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:207)
- [migration (line 290)](D:\\Projects\\LotusSmartStudy\\backend\\alembic\\versions\\0001_class8_pilot_schema.py:290)
Concurrent requests can both pass the page-count check and receive the same order. Completion may then produce an unhandled uniqueness error.
M-02 — Object deletion precedes the database commit
- [student_api.py (line 272)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:272)
- [student_api.py (line 281)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:281)
If the database transaction fails after object deletion, the restored database row points to a missing object.
M-03 — Presigned uploads do not constrain actual uploaded size
- [storage.py (line 48)](D:\\Projects\\LotusSmartStudy\\backend\\app\\storage.py:48)
- [student_api.py (line 200)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:200)
The API validates the client-declared size, but the signed PUT does not enforce a content-length range. A student can upload a much larger object and abandon it without completing validation. Bucket lifecycle cleanup reduces but does not eliminate the storage-abuse risk.
M-04 — Question rejection and test publication are not serialized
- [tests_api.py (line 158)](D:\\Projects\\LotusSmartStudy\\backend\\app\\tests_api.py:158)
- [tests_api.py (line 164)](D:\\Projects\\LotusSmartStudy\\backend\\app\\tests_api.py:164)
- [router.py (line 200)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\router.py:200)
Publication locks the test but not the included question rows. Concurrent rejection can race with publication, producing a published snapshot from a question that ends in Rejected status.
M-05 — Enabled topics may have no extracted content
- [ingestion.py (line 67)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:67)
- [ingestion.py (line 94)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:94)
- [ingestion.py (line 109)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:109)
Every taxonomy topic is enabled, but ingestion verifies only that the chapter produced some chunks. A heading missed by the exact regex can leave an enabled topic with zero content, causing generation to fail only after the teacher selects it.
M-06 — Re-ingestion can retain stale or withdrawn textbook chunks
- [ingestion.py (line 92)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:92)
- [ingestion.py (line 197)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:197)
- [ingestion.py (line 214)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:214)
- [retrieval.py (line 64)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\retrieval.py:64)
A changed PDF receives a new checksum-based document ID without retiring its predecessor. Removed documents are also not retired. Retrieval can later mix current and obsolete content.
M-07 — Teacher rewrites retain the original AI provenance
- [router.py (line 140)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\router.py:140)
- [router.py (line 232)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\router.py:232)
A teacher can materially rewrite question content while source_trace and validation flags continue to represent the original AI output. Edited questions should be identified as teacher-modified or revalidated.
M-08 — Nested retry loops can produce up to nine provider calls
- [provider.py (line 72)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\provider.py:72)
- [service.py (line 109)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\service.py:109)
- [config.py (line 39)](D:\\Projects\\LotusSmartStudy\\backend\\app\\config.py:39)
Transport retries and validation retries multiply. With both configured to two and a 90-second timeout, one browser request can occupy a worker for roughly 13.5 minutes.
M-09 — Generation batches can become stranded in the UI
- [generation page (line 6)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\generate\\page.tsx:6)
- [teacher dashboard (line 3)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\page.tsx:3)
The frontend waits synchronously for generation before navigating to the batch. A browser or proxy timeout after batch creation loses the navigation target, and no batch-history screen exists.
M-10 — Answer-length configuration is inconsistent
- [attempt page (line 144)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\student\\attempts[id]\\page.tsx:144)
- [config.py (line 21)](D:\\Projects\\LotusSmartStudy\\backend\\app\\config.py:21)
- [student_api.py (line 132)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:132)
The frontend always limits answers to 4,000 characters while the backend limit is configurable.
M-11 — Login has no brute-force throttling
- [auth.py (line 17)](D:\\Projects\\LotusSmartStudy\\backend\\app\\auth.py:17)
- [security.py (line 20)](D:\\Projects\\LotusSmartStudy\\backend\\app\\security.py:20)
Password verification is appropriately generic and uses scrypt, but there is no per-account or per-source throttling. This should be implemented in the application or guaranteed by the deployment gateway.
Low
- Duplicate question IDs can reach a database uniqueness error instead of returning a validation error: [tests_api.py (line 50)](D:\\Projects\\LotusSmartStudy\\backend\\app\\tests_api.py:50).
- Expired sessions do not automatically reset frontend authentication state after a protected request returns 401: [api.ts (line 10)](D:\\Projects\\LotusSmartStudy\\frontend\\lib\\api.ts:10), [AuthProvider.tsx (line 16)](D:\\Projects\\LotusSmartStudy\\frontend\\components\\AuthProvider.tsx:16).
- Generation settings loaded through application settings do not receive all bounds validation used by the alternate environment loader: [settings.py (line 27)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\settings.py:27), [settings.py (line 43)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\settings.py:43).
Use-case coverage
Use case	Review result
UC-01 Teacher Login	Implemented; rate limiting missing
UC-02 Student Login	Implemented; rate limiting missing
UC-03 Teacher Dashboard	Implemented; integration aligned
UC-04 Student Dashboard	Implemented; published-result filtering aligned
UC-05 Configure Generation	Implemented; unbounded counts
UC-06 Generate Questions	Blocked by C-01; topic and retry risks
UC-07 Review/Approve	Implemented; visible-edit approval mismatch
UC-08 Publish Test	Implemented; approval/rejection race
UC-09 MCQ Answer	Implemented; DTO and autosave route aligned
UC-10 Typed Answer	Implemented; pending text can be lost
UC-11 Photo Upload	Implemented; concurrency, resource, and object-consistency issues
UC-12 Submit Test	Implemented; image race violates final immutability
UC-13 Answer Sheet	Implemented; authorization aligned, but image race can alter content
UC-14 Manual Evaluation	Implemented; failed-save UI can misrepresent persisted marks
UC-15 Publish Result	Implemented; can publish stale marks after failed autosave
UC-16 View Result	Implemented; ownership and publication checks aligned


Positive findings
- ORM models and the baseline Alembic migration are closely aligned.
- Class 8 and Term 1/Term 2 scope is enforced.
- Exact term/chapter/topic ancestry is checked without retrieval fallback.
- Student APIs exclude reference answers and intended MCQ answers.
- Teacher and student ownership checks are consistently applied server-side.
- Passwords use salted scrypt hashes; sessions use hashed opaque tokens and secure production cookies.
- One-attempt, answer, evaluation, assignment, and result uniqueness constraints are present.
- Frozen test snapshots and server-calculated result totals are implemented.
- Results remain inaccessible until publication.
- AI marking and automatic MCQ scoring are absent as required.
- Class 12, scheduling, timers, Twist, and result reopening remain excluded.
Final verdict: remediation required before manual acceptance testing. At minimum, fix C-01 and H-01 through H-06, then perform the owner-run migration, ingestion verification, build, and end-to-end tests.Final Read-Only Technical Review
Recommendation: not ready for full manual end-to-end testing yet.

All 16 use cases have implementation paths, and the overall architecture is coherent. However, one Critical AI-provider incompatibility will likely prevent question generation entirely, and several High findings can cause incorrect approval, incorrect published marks, lost student answers, or post-submission answer mutation.

Environment preparation can begin, but the Critical and High findings should be corrected before an acceptance-testing cycle.

No files were modified. No dependencies, builds, tests, migrations, servers, provider calls, or deployments were executed.
Critical
C-01 — OpenAI strict structured-output schema is incompatible
The provider submits a raw Pydantic JSON schema with strict: true:
- [provider.py (line 56)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\provider.py:56)
- [contracts.py (line 77)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\contracts.py:77)
- [prompts.py (line 52)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\prompts.py:52)
Several model fields have defaults and therefore are not included as required fields, while generated object schemas do not consistently declare additionalProperties: false.

Current official OpenAI Structured Outputs documentation requires every field to be required and every object to set additionalProperties: false when strict mode is used. An unsupported strict schema receives an API error.

Expected impact: question generation and regeneration are likely to fail with an OpenAI HTTP 400, blocking UC-06 and part of UC-07.
High
H-01 — Generation counts have no server-side maximum
- [contracts.py (line 32)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\contracts.py:32)
- [service.py (line 162)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\service.py:162)
- [generation page (line 7)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\generate\\page.tsx:7)
Per-type counts require only >= 0. An authenticated teacher can request an extremely large batch, causing excessive memory, CPU, prompt size, and provider cost. Enforce per-type and aggregate limits on the backend.
H-02 — The UI can approve content different from the visible edits
- [batch review page (line 10)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\batches[id]\\page.tsx:10)
- [batch review page (line 19)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\batches[id]\\page.tsx:19)
- [batch review page (line 37)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\batches[id]\\page.tsx:37)
- [batch review page (line 47)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\batches[id]\\page.tsx:47)
- [router.py (line 188)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\router.py:188)
Edits live locally until “Save edits” succeeds. The teacher can change a question and click “Approve” without saving; approval then applies to the old server version while the edited version remains visible. A failed save produces the same risk.

This violates the teacher-control expectation in UC-07.
H-03 — Failed evaluation autosaves can publish stale server marks
- [evaluation page (line 27)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\evaluations[id]\\page.tsx:27)
- [evaluation page (line 31)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\evaluations[id]\\page.tsx:31)
- [evaluation page (line 38)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\evaluations[id]\\page.tsx:38)
- [evaluation page (line 50)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\evaluations[id]\\page.tsx:50)
- [evaluation page (line 74)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\evaluations[id]\\page.tsx:74)
- [teacher_api.py (line 133)](D:\\Projects\\LotusSmartStudy\\backend\\app\\teacher_api.py:133)
The frontend keeps locally edited marks after a save failure. It can still show the attempt as complete and enable publication. The backend publishes the previously persisted evaluations, so the published total can differ from the teacher’s confirmation dialog.

This affects UC-14 and UC-15.
H-04 — Recent typed answers can be lost during navigation or unload
- [attempt page (line 47)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\student\\attempts[id]\\page.tsx:47)
- [attempt page (line 76)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\student\\attempts[id]\\page.tsx:76)
- [attempt page (line 79)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\student\\attempts[id]\\page.tsx:79)
Unmount cleanup cancels the debounce timer without flushing the pending text. Reload, browser back, tab close, or navigation outside the test within the debounce interval loses the latest edit despite displaying “Saving…”.

This fails part of UC-10’s persistence acceptance criterion.
H-05 — Image mutations can commit after submission
- [student_api.py (line 156)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:156)
- [student_api.py (line 182)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:182)
- [student_api.py (line 192)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:192)
- [student_api.py (line 216)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:216)
- [student_api.py (line 249)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:249)
- [student_api.py (line 266)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:266)
Submission locks the attempt row, but upload creation, completion, reordering, and deletion do not use that lock. An image operation can verify in_progress, submission can commit, and the image operation can then commit afterward.

This can mutate the teacher-visible answer after submission, violating UC-12 and UC-13 immutability.
H-06 — Configured pixel limits are checked after image decoding
- [storage.py (line 71)](D:\\Projects\\LotusSmartStudy\\backend\\app\\storage.py:71)
- [storage.py (line 76)](D:\\Projects\\LotusSmartStudy\\backend\\app\\storage.py:76)
- [storage.py (line 83)](D:\\Projects\\LotusSmartStudy\\backend\\app\\storage.py:83)
The image is fully loaded before width × height is compared with the configured limit. A small compressed decompression-bomb image can consume substantial memory before rejection, potentially exhausting an API worker.
Medium
M-01 — Concurrent image grants can exceed limits or collide on page order
- [student_api.py (line 202)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:202)
- [student_api.py (line 207)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:207)
- [migration (line 290)](D:\\Projects\\LotusSmartStudy\\backend\\alembic\\versions\\0001_class8_pilot_schema.py:290)
Concurrent requests can both pass the page-count check and receive the same order. Completion may then produce an unhandled uniqueness error.
M-02 — Object deletion precedes the database commit
- [student_api.py (line 272)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:272)
- [student_api.py (line 281)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:281)
If the database transaction fails after object deletion, the restored database row points to a missing object.
M-03 — Presigned uploads do not constrain actual uploaded size
- [storage.py (line 48)](D:\\Projects\\LotusSmartStudy\\backend\\app\\storage.py:48)
- [student_api.py (line 200)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:200)
The API validates the client-declared size, but the signed PUT does not enforce a content-length range. A student can upload a much larger object and abandon it without completing validation. Bucket lifecycle cleanup reduces but does not eliminate the storage-abuse risk.
M-04 — Question rejection and test publication are not serialized
- [tests_api.py (line 158)](D:\\Projects\\LotusSmartStudy\\backend\\app\\tests_api.py:158)
- [tests_api.py (line 164)](D:\\Projects\\LotusSmartStudy\\backend\\app\\tests_api.py:164)
- [router.py (line 200)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\router.py:200)
Publication locks the test but not the included question rows. Concurrent rejection can race with publication, producing a published snapshot from a question that ends in Rejected status.
M-05 — Enabled topics may have no extracted content
- [ingestion.py (line 67)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:67)
- [ingestion.py (line 94)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:94)
- [ingestion.py (line 109)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:109)
Every taxonomy topic is enabled, but ingestion verifies only that the chapter produced some chunks. A heading missed by the exact regex can leave an enabled topic with zero content, causing generation to fail only after the teacher selects it.
M-06 — Re-ingestion can retain stale or withdrawn textbook chunks
- [ingestion.py (line 92)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:92)
- [ingestion.py (line 197)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:197)
- [ingestion.py (line 214)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\ingestion.py:214)
- [retrieval.py (line 64)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\retrieval.py:64)
A changed PDF receives a new checksum-based document ID without retiring its predecessor. Removed documents are also not retired. Retrieval can later mix current and obsolete content.
M-07 — Teacher rewrites retain the original AI provenance
- [router.py (line 140)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\router.py:140)
- [router.py (line 232)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\router.py:232)
A teacher can materially rewrite question content while source_trace and validation flags continue to represent the original AI output. Edited questions should be identified as teacher-modified or revalidated.
M-08 — Nested retry loops can produce up to nine provider calls
- [provider.py (line 72)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\provider.py:72)
- [service.py (line 109)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\service.py:109)
- [config.py (line 39)](D:\\Projects\\LotusSmartStudy\\backend\\app\\config.py:39)
Transport retries and validation retries multiply. With both configured to two and a 90-second timeout, one browser request can occupy a worker for roughly 13.5 minutes.
M-09 — Generation batches can become stranded in the UI
- [generation page (line 6)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\generate\\page.tsx:6)
- [teacher dashboard (line 3)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\teacher\\page.tsx:3)
The frontend waits synchronously for generation before navigating to the batch. A browser or proxy timeout after batch creation loses the navigation target, and no batch-history screen exists.
M-10 — Answer-length configuration is inconsistent
- [attempt page (line 144)](D:\\Projects\\LotusSmartStudy\\frontend\\app\\student\\attempts[id]\\page.tsx:144)
- [config.py (line 21)](D:\\Projects\\LotusSmartStudy\\backend\\app\\config.py:21)
- [student_api.py (line 132)](D:\\Projects\\LotusSmartStudy\\backend\\app\\student_api.py:132)
The frontend always limits answers to 4,000 characters while the backend limit is configurable.
M-11 — Login has no brute-force throttling
- [auth.py (line 17)](D:\\Projects\\LotusSmartStudy\\backend\\app\\auth.py:17)
- [security.py (line 20)](D:\\Projects\\LotusSmartStudy\\backend\\app\\security.py:20)
Password verification is appropriately generic and uses scrypt, but there is no per-account or per-source throttling. This should be implemented in the application or guaranteed by the deployment gateway.
Low
- Duplicate question IDs can reach a database uniqueness error instead of returning a validation error: [tests_api.py (line 50)](D:\\Projects\\LotusSmartStudy\\backend\\app\\tests_api.py:50).
- Expired sessions do not automatically reset frontend authentication state after a protected request returns 401: [api.ts (line 10)](D:\\Projects\\LotusSmartStudy\\frontend\\lib\\api.ts:10), [AuthProvider.tsx (line 16)](D:\\Projects\\LotusSmartStudy\\frontend\\components\\AuthProvider.tsx:16).
- Generation settings loaded through application settings do not receive all bounds validation used by the alternate environment loader: [settings.py (line 27)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\settings.py:27), [settings.py (line 43)](D:\\Projects\\LotusSmartStudy\\backend\\app\\generation\\settings.py:43).
Use-case coverage
Use case	Review result
UC-01 Teacher Login	Implemented; rate limiting missing
UC-02 Student Login	Implemented; rate limiting missing
UC-03 Teacher Dashboard	Implemented; integration aligned
UC-04 Student Dashboard	Implemented; published-result filtering aligned
UC-05 Configure Generation	Implemented; unbounded counts
UC-06 Generate Questions	Blocked by C-01; topic and retry risks
UC-07 Review/Approve	Implemented; visible-edit approval mismatch
UC-08 Publish Test	Implemented; approval/rejection race
UC-09 MCQ Answer	Implemented; DTO and autosave route aligned
UC-10 Typed Answer	Implemented; pending text can be lost
UC-11 Photo Upload	Implemented; concurrency, resource, and object-consistency issues
UC-12 Submit Test	Implemented; image race violates final immutability
UC-13 Answer Sheet	Implemented; authorization aligned, but image race can alter content
UC-14 Manual Evaluation	Implemented; failed-save UI can misrepresent persisted marks
UC-15 Publish Result	Implemented; can publish stale marks after failed autosave
UC-16 View Result	Implemented; ownership and publication checks aligned


Positive findings
- ORM models and the baseline Alembic migration are closely aligned.
- Class 8 and Term 1/Term 2 scope is enforced.
- Exact term/chapter/topic ancestry is checked without retrieval fallback.
- Student APIs exclude reference answers and intended MCQ answers.
- Teacher and student ownership checks are consistently applied server-side.
- Passwords use salted scrypt hashes; sessions use hashed opaque tokens and secure production cookies.
- One-attempt, answer, evaluation, assignment, and result uniqueness constraints are present.
- Frozen test snapshots and server-calculated result totals are implemented.
- Results remain inaccessible until publication.
- AI marking and automatic MCQ scoring are absent as required.
- Class 12, scheduling, timers, Twist, and result reopening remain excluded.
Final verdict: remediation required before manual acceptance testing. At minimum, fix C-01 and H-01 through H-06, then perform the owner-run migration, ingestion verification, build, and end-to-end tests.

## Remediation status - 2026-11-01

The findings above are the original read-only review record. The current source
now contains remediation for every listed item:

- **Critical:** C-01 resolved with an OpenAI-compatible strict schema tree.
- **High:** H-01 through H-06 resolved in generation limits, approval/evaluation
  persistence, student draft recovery, image locking, and image safety.
- **Medium:** M-01 through M-11 resolved through upload serialization and signed
  POST limits, database-first deletion, publication locks, ingestion/current
  source checks, provenance flags, bounded retries, teacher-visible recent
  batches, shared answer limits, and PostgreSQL-backed account throttling
  across API workers.
- **Low:** duplicate question IDs now receive 422, frontend authentication reacts
  to expired sessions, and generation settings use consistent validation.

Runtime validation remains pending because project restrictions prohibit Codex
from running builds, tests, migrations, servers, provider requests, or
deployments. Follow `docs/MANUAL_SETUP.md` for the owner-run validation sequence.
