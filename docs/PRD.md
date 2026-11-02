**LOTUS SMART STUDY**

> **Approved platform expansion - 2 November 2026:** The assessment workflow
> and all 16 use cases in this baseline now apply to configured curricula for
> Classes 8-12 across CBSE, ICSE, and separately identified State Boards.
> Generation remains disabled unless the selected textbook and chapter have
> processed source content. Existing CBSE Class 8 Mathematics content remains
> the only preloaded curriculum; no syllabus, subject, textbook, or chapter is
> inferred for other selections. This approval supersedes older Class 8/Class
> 12 Mathematics-only and board-specific scope statements below, while all
> explicit workflow exclusions remain in force.

**Pilot MVP Requirements & Use-Case Implementation**

CBSE Mathematics Test Generation, Student Assessment & Manual Evaluation

| Pilot objective: Prove one complete academic workflow with the smallest usable product: teacher generates CBSE-style Mathematics questions, reviews and publishes a test, students answer using MCQ/text/photo, teacher manually evaluates, and students receive the result. |
| :---- |

| Scope item | Pilot MVP |
| :---- | :---- |
| Roles | Teacher and Student only |
| Classes / subject | CBSE Class 8 and Class 12 Mathematics |
| AI responsibility | Question generation only |
| Question control | Teacher reviews and approves before publishing |
| Student answers | MCQ selection, short typed answer, handwritten solution photo upload |
| Evaluation | Teacher manually marks correct/wrong and enters awarded marks |
| Result | Published per test and visible in student dashboard/history |
| Analytics | Only essential dashboard KPIs and test/result access |

Version 1.0 • Pilot MVP Baseline • October 2026

# **1\. Product Definition**

Lotus Smart Study Pilot MVP is a responsive web application for conducting teacher-controlled Mathematics assessments. It is not a school profile website and it is not a full LMS. The pilot validates the end-to-end assessment cycle and, especially, whether AI can repeatedly generate useful, syllabus-grounded, CBSE-style questions that teachers are willing to approve.

| Non-negotiable generation rule: Random generation must mean genuinely different question framing and reasoning—not the same sum with only numbers changed. The selected textbook/source controls what can be tested; CBSE references guide how questions are framed. |
| :---- |

# **2\. Frozen Pilot MVP Scope**

| \# | Capability | What is included |
| :---- | :---- | :---- |
| 1 | Login | Teacher and Student authentication with role-specific access. |
| 2 | Dashboard / KPI | Teacher test/submission/evaluation KPIs; Student available/completed test and result access. |
| 3 | Question Generation | Teacher configures class/chapter/question types/counts/marks/difficulty/style and generates AI questions. |
| 4 | Review & Approve | Teacher reviews, edits/regenerates where needed, approves and publishes questions as a test. |
| 5 | Student Test | MCQ selection, short typed answer, and handwritten answer image upload for full sums/case studies. |
| 6 | Manual Evaluation | Teacher sees each answer, marks correct/wrong, enters marks and optional comment. |
| 7 | Result | Teacher publishes result; student sees test-wise total and question-wise marks/status. |

# **3\. Explicitly Not in Pilot MVP**

* Separate Admin portal and complex academic-year management.  
* Reusable enterprise question bank and advanced search.  
* AI answer evaluation or automatic final marking.  
* Automatic MCQ scoring (can be added later; pilot keeps teacher evaluation consistent and manual).  
* Parent portal, payments, subscriptions, notifications by WhatsApp/SMS/email.  
* Adaptive learning, weak-area recommendations, AI tutor and predictive analytics.  
* Advanced reports, competency dashboards and long-term learning analytics.  
* Native Android/iOS apps; responsive web application is sufficient.  
* PDF question-paper generation and printing workflow.  
* Other boards, subjects or classes beyond the pilot.

# **4\. Roles**

| Teacher | Student |
| :---- | :---- |
| Login and dashboard | Login and dashboard |
| Configure/generate questions | View available tests |
| Review/edit/regenerate/approve | Start and take assigned test |
| Create/publish test | Select MCQ / type short answer |
| View submissions | Upload handwritten answer photos |
| Manually evaluate and enter marks | Submit test |
| Publish result | View published result/history |

# **5\. End-to-End Pilot Workflow**

1. Teacher logs in.  
2. Teacher creates a test-generation configuration.  
3. AI generates draft questions using the selected syllabus/source and CBSE-style guidance.  
4. Teacher reviews each question and edits, regenerates or approves it.  
5. Teacher publishes the approved test to selected students/class.  
6. Student logs in and opens the available test.  
7. Student answers MCQs, types short answers, and uploads notebook photos for long sums/case studies.  
8. Student submits the test.  
9. Teacher opens the submitted answer sheet and manually evaluates each question.  
10. Teacher marks Correct/Wrong, enters awarded marks and optionally adds feedback.  
11. System totals the teacher-entered marks.  
12. Teacher publishes the result.  
13. Student sees the result on the dashboard and test-result page.

# **6\. Detailed Use Cases and Implementation**

### **UC-01 — Teacher Login**

| Field | Details |
| :---- | :---- |
| Actor | Teacher |
| Goal | Securely access teacher functions. |
| Pre-condition | Teacher account already exists and is active. |

**User flow**

14. Open login page.  
15. Enter login credentials.  
16. Submit.  
17. System validates credentials and role.  
18. Redirect to Teacher Dashboard.

**Implementation notes**

* Use one authentication service/table with role field.  
* Protect all teacher APIs/routes server-side, not only in UI.  
* Persist authenticated session securely.  
* Provide logout.

**Validations / rules**

* Invalid credentials show generic error.  
* Inactive/student account cannot enter teacher area.

**Acceptance criteria**

* Valid teacher reaches dashboard.  
* Unauthorized access to teacher URL/API is blocked.  
* Logout ends access.

### **UC-02 — Student Login**

| Field | Details |
| :---- | :---- |
| Actor | Student |
| Goal | Securely access assigned tests and results. |
| Pre-condition | Student account exists and is active. |

**User flow**

19. Open login page.  
20. Enter credentials.  
21. Submit.  
22. System validates role.  
23. Redirect to Student Dashboard.

**Implementation notes**

* Reuse authentication layer from UC-01.  
* Student queries must always be scoped to logged-in student ID.

**Validations / rules**

* Student cannot access another student's attempts/results.  
* Inactive account cannot log in.

**Acceptance criteria**

* Valid student reaches own dashboard.  
* Teacher-only routes are inaccessible.

### **UC-03 — Teacher Dashboard / KPIs**

| Field | Details |
| :---- | :---- |
| Actor | Teacher |
| Goal | See current test workflow and quickly access work. |
| Pre-condition | Teacher is logged in. |

**User flow**

24. Open dashboard.  
25. View KPI cards.  
26. Open recent test or pending evaluation from dashboard.

**Implementation notes**

* Minimum KPIs: Total Tests, Active/Published Tests, Submitted Attempts, Pending Evaluation.  
* Show recent tests with status and quick actions.  
* KPIs derive from actual test/attempt/evaluation records.

**Validations / rules**

* Only teacher-owned/assigned tests are counted.

**Acceptance criteria**

* Counts match underlying records.  
* Pending Evaluation opens relevant submissions.

### **UC-04 — Student Dashboard / Result Access**

| Field | Details |
| :---- | :---- |
| Actor | Student |
| Goal | See available tests and completed results. |
| Pre-condition | Student is logged in. |

**User flow**

27. Open dashboard.  
28. View Available Tests and Completed Tests.  
29. Start an available test or open a published result.

**Implementation notes**

* Minimum KPI/cards: Available Tests, Completed Tests; optional Average Score if at least one result exists.  
* Do not expose draft/unpublished results.

**Validations / rules**

* Only assigned tests are visible.  
* Closed/unavailable tests cannot be started.

**Acceptance criteria**

* Student sees correct test status.  
* Published results are accessible from history.

### **UC-05 — Configure Question Generation**

| Field | Details |
| :---- | :---- |
| Actor | Teacher |
| Goal | Define exactly what type of test/questions AI should create. |
| Pre-condition | Teacher is logged in and source/reference content is available to generation service. |

**User flow**

30. Click Create/Generate Test.  
31. Choose Class 8 or 12 and Mathematics.  
32. Choose chapter/topic scope.  
33. Configure question types and counts.  
34. Choose difficulty/style.  
35. Click Generate.

**Implementation notes**

* Configurable types: MCQ, 1-mark, 2-mark, 3-mark, 5-mark, Case Study.  
* Teacher can choose count for each enabled type.  
* Support Easy/Medium/Hard/Mixed and Standard/CBSE Style/Challenging.  
* Store generation configuration with generated batch.

**Validations / rules**

* Counts must be non-negative integers.  
* At least one question required.  
* Selected chapter/topic must belong to selected class.  
* Total marks calculated before generation.

**Acceptance criteria**

* Valid configuration starts generation.  
* Generated batch retains exact configuration used.

### **UC-06 — Generate Random / Twisted CBSE-Style Questions**

| Field | Details |
| :---- | :---- |
| Actor | Teacher/System |
| Goal | Create new, syllabus-correct questions that reflect CBSE asking patterns. |
| Pre-condition | UC-05 configuration is valid. |

**User flow**

36. System retrieves relevant textbook/source content.  
37. System retrieves relevant CBSE pattern/reference guidance.  
38. AI generates candidate questions.  
39. System performs basic validation/similarity checks.  
40. Draft questions are returned to teacher review.

**Implementation notes**

* Textbook/source answers WHAT can be tested; CBSE references guide HOW it is asked.  
* Variation should include direct, reverse, application, reasoning, multi-step, competency/HOTS and case-study framing where suitable.  
* Changing numbers alone is not considered sufficient variation.  
* Store question text, type, marks, options where applicable, teacher reference answer/solution, chapter/topic, difficulty and style.  
* For MCQ, generate plausible distractors and one intended correct option.  
* For case study, generate coherent scenario plus linked sub-question(s).

**Validations / rules**

* Do not introduce out-of-syllabus concepts to make a question hard.  
* Question marks should match expected solution depth.  
* If generated item is malformed/duplicate/unsupported, regenerate or flag it.  
* All generated questions begin as Draft.

**Acceptance criteria**

* Repeated generation produces materially different questions.  
* Every question is traceable to selected chapter/topic.  
* Teacher receives a reference answer/solution for review.

### **UC-07 — Review, Edit, Regenerate and Approve Questions**

| Field | Details |
| :---- | :---- |
| Actor | Teacher |
| Goal | Ensure no AI-generated question reaches students without teacher control. |
| Pre-condition | Generated draft batch exists. |

**User flow**

41. Open generated test.  
42. Review each question and metadata.  
43. Approve as-is, edit, regenerate/replace, or reject.  
44. Continue until required questions are approved.  
45. Proceed to publish.

**Implementation notes**

* Review card shows question, marks, type, chapter/topic, difficulty and teacher answer.  
* Teacher may edit text/options/marks/reference answer.  
* Regenerate replaces one question, not whole test.  
* Optional Twist action keeps concept/marks but changes framing.  
* Statuses: Draft, Approved, Rejected.

**Validations / rules**

* Only Approved questions can be published.  
* MCQ must have valid options/correct answer after edit.  
* Total marks recalculates if marks change.

**Acceptance criteria**

* Teacher can complete review without leaving page.  
* Unapproved question blocks publication.

### **UC-08 — Publish Test to Students**

| Field | Details |
| :---- | :---- |
| Actor | Teacher |
| Goal | Make approved test available to intended students. |
| Pre-condition | All included questions are Approved. |

**User flow**

46. Enter test title and basic instructions.  
47. Choose students/class/batch using pilot's available grouping.  
48. Optionally set duration/availability if included in pilot build.  
49. Click Publish.  
50. Students see test as Available.

**Implementation notes**

* Minimum test data: title, questions, total marks, assigned students, status, created/published timestamps.  
* Status: Draft → Published → Submitted/Evaluation context → Result Published.  
* Keep assignment simple; no complex scheduling is required for first pilot unless desired.

**Validations / rules**

* Cannot publish empty test or unapproved questions.  
* Student not assigned to test cannot access it.

**Acceptance criteria**

* Published test appears for assigned students.  
* Question content is frozen for submitted attempts.

### **UC-09 — Student Answers MCQ**

| Field | Details |
| :---- | :---- |
| Actor | Student |
| Goal | Answer a multiple-choice question. |
| Pre-condition | Student has started an assigned published test. |

**User flow**

51. Read question.  
52. Select one option.  
53. Navigate to another question; selection is saved.

**Implementation notes**

* Store selected option ID/value against attempt and question.  
* Autosave on selection/navigation.

**Validations / rules**

* Only one option selectable for single-choice MCQ.  
* Do not reveal correct answer during test.

**Acceptance criteria**

* Selection persists after navigation/refresh where session is valid.

### **UC-10 — Student Types Short Answer**

| Field | Details |
| :---- | :---- |
| Actor | Student |
| Goal | Submit a one-line/short text answer. |
| Pre-condition | Student is in an active attempt. |

**User flow**

54. Read question.  
55. Type answer in text field.  
56. Navigate; answer is saved.

**Implementation notes**

* Use simple text input/textarea for pilot.  
* Support normal mathematical characters entered by keyboard where possible.  
* No AI validation/scoring at submission.

**Validations / rules**

* Apply reasonable length limit but do not over-restrict Maths notation.  
* Empty answer is allowed but shown as unanswered.

**Acceptance criteria**

* Typed answer persists and teacher can read it exactly as submitted.

### **UC-11 — Student Uploads Handwritten Solution Photos**

| Field | Details |
| :---- | :---- |
| Actor | Student |
| Goal | Submit full working for long sums and case-study questions without a complex equation editor. |
| Pre-condition | Student is in an active attempt and question permits image answer. |

**User flow**

57. Solve on notebook/paper.  
58. Tap Take Photo or Upload Image.  
59. Preview uploaded page.  
60. Add more pages if needed.  
61. Replace/remove a page before final submission.

**Implementation notes**

* Allow multiple images per question and maintain page order.  
* On mobile, file input should support camera capture where browser/device allows.  
* Compress/resize large images server-side while preserving readable resolution.  
* Store images in object/file storage; database stores metadata/path, not binary blob.  
* Show upload progress and success state.

**Validations / rules**

* Allow common image formats such as JPEG/PNG/WebP.  
* Set practical file-size/page-count limits configurable by system.  
* Reject unsupported/corrupt files with clear error.  
* Student must be able to preview uploaded image before submission.

**Acceptance criteria**

* Teacher receives every uploaded page in correct order.  
* Images remain readable when zoomed.  
* Student can replace wrong photo before submit.

### **UC-12 — Submit Student Test**

| Field | Details |
| :---- | :---- |
| Actor | Student |
| Goal | Finalize answers and send them for teacher evaluation. |
| Pre-condition | Student has an active attempt. |

**User flow**

62. Click Submit Test.  
63. System shows confirmation and unanswered count.  
64. Student confirms.  
65. System locks answers and marks attempt Submitted.  
66. Teacher sees it in Pending Evaluation.

**Implementation notes**

* Submission endpoint must be idempotent.  
* Record submitted timestamp.  
* After submission, answer records and images are read-only to student.

**Validations / rules**

* Do not silently lose unsaved/uploading image.  
* Repeated submit must not create duplicate attempt.

**Acceptance criteria**

* Submitted attempt appears once in teacher queue.  
* Student sees Submitted status.

### **UC-13 — Teacher Opens Student Answer Sheet**

| Field | Details |
| :---- | :---- |
| Actor | Teacher |
| Goal | Review one student's complete submitted test. |
| Pre-condition | Student attempt status is Submitted. |

**User flow**

67. Open Pending Evaluation.  
68. Choose test/student.  
69. System displays question and corresponding student answer.  
70. Navigate question-by-question.

**Implementation notes**

* For MCQ show selected option; for short answer show typed text; for photo answer show ordered image gallery.  
* Show question maximum marks and teacher reference answer/solution.  
* Images should open in larger viewer with zoom.

**Validations / rules**

* Teacher cannot accidentally modify student's submitted answer.

**Acceptance criteria**

* All submitted answer types display correctly.  
* Teacher can move between questions without losing evaluation work.

### **UC-14 — Manual Correct/Wrong and Mark Entry**

| Field | Details |
| :---- | :---- |
| Actor | Teacher |
| Goal | Manually evaluate each student answer. |
| Pre-condition | Teacher has opened a submitted attempt. |

**User flow**

71. Review answer.  
72. Choose Correct or Wrong (or status appropriate to partial marks).  
73. Enter awarded marks.  
74. Optionally type feedback.  
75. Save and move to next question.

**Implementation notes**

* Teacher decision is authoritative; no AI scoring.  
* Awarded marks stored per question/sub-question.  
* Allow partial marks even when overall status is Wrong/Partial; implementation may use Correct / Wrong / Partial for clarity.  
* Autosave evaluation entries.  
* Display maximum marks beside input.

**Validations / rules**

* Awarded marks \>= 0 and \<= question maximum.  
* Warn if a question has no mark before finalization.  
* Correct/Wrong status and marks must not conflict silently; allow teacher override with clear state.

**Acceptance criteria**

* Saved marks survive navigation/re-login.  
* System total equals sum of teacher-entered marks.

### **UC-15 — Finalize and Publish Result**

| Field | Details |
| :---- | :---- |
| Actor | Teacher |
| Goal | Complete evaluation and release result to student. |
| Pre-condition | Required questions have teacher-entered marks. |

**User flow**

76. Review total.  
77. Click Finalize/Publish Result.  
78. System records total and result status.  
79. Student gains access to result.

**Implementation notes**

* Store evaluator, total, max marks, publish timestamp and optional overall comment.  
* Once published, edits should require an explicit Reopen/Edit Result action if pilot supports corrections.

**Validations / rules**

* Block publish if required questions are unmarked unless teacher explicitly resolves them.

**Acceptance criteria**

* Published result appears immediately on student's completed-test list.  
* Total is mathematically correct.

### **UC-16 — Student Views Test Result**

| Field | Details |
| :---- | :---- |
| Actor | Student |
| Goal | Understand performance on a completed test. |
| Pre-condition | Teacher has published result. |

**User flow**

80. Open Completed Tests.  
81. Select test.  
82. View total score and question-wise result.

**Implementation notes**

* Show test name, marks obtained/max, percentage, and question-wise awarded marks.  
* Show Correct/Wrong/Partial status and teacher feedback if entered.  
* Teacher reference answer can remain hidden in pilot unless explicitly enabled.

**Validations / rules**

* Unpublished evaluation data must never be visible.

**Acceptance criteria**

* Student sees only own result.  
* Displayed total matches teacher-published total.

# **7\. Question Generation Rules for Pilot**

| Rule | Requirement |
| :---- | :---- |
| Content boundary | Generate only from selected Class 8/12 Mathematics chapter/topic source material. |
| CBSE style | Use maintained CBSE examples/pattern guidance to imitate question approach, not copy questions. |
| Randomness | A new paper should change structure/reasoning/context, not only numeric values. |
| Difficulty | Harder questions must remain within syllabus. |
| Marks alignment | 1/2/3/5-mark questions should require proportionate working/depth. |
| MCQ quality | One intended correct answer; plausible distractors. |
| Case study | Meaningful scenario plus linked mathematical sub-question(s). |
| Teacher control | Every generated question remains Draft until teacher approval. |
| Reference solution | Generate teacher-facing answer/solution for review/evaluation assistance. |
| No AI marking | Reference answer does not automatically assign student marks in Pilot MVP. |

# **8\. Minimum Screens**

| Teacher | Student |
| :---- | :---- |
| Login | Login |
| Teacher Dashboard | Student Dashboard |
| Generate Test / Configuration | Available Tests |
| Generated Question Review | Test Instructions / Start |
| Publish Test | Test Player |
| Pending Evaluations | Photo Upload / Preview within Test Player |
| Student Answer Sheet / Evaluation | Submission Confirmation |
| Publish Result | Completed Tests |
| Test Result / basic summary | Test Result Detail |

# **9\. Minimal Data Model**

| Entity | Minimum fields |
| :---- | :---- |
| User | id, name, login identifier, password hash/auth id, role, status |
| Class/Student Mapping | student\_id, class, optional batch/section |
| Source Content | class, subject, chapter/topic, indexed content/reference |
| Generation Batch | teacher\_id, configuration JSON/fields, created\_at |
| Question | batch\_id, text, type, marks, options, correct/reference answer, chapter/topic, difficulty, status |
| Test | teacher\_id, title, total\_marks, status, published\_at |
| Test Question | test\_id, question\_id, order, marks |
| Test Assignment | test\_id, student\_id |
| Attempt | test\_id, student\_id, started\_at, submitted\_at, status |
| Student Answer | attempt\_id, question\_id, text/selected\_option, answer\_type |
| Answer Image | student\_answer\_id, file\_path/url, page\_order, uploaded\_at |
| Question Evaluation | attempt\_id, question\_id, result\_status, awarded\_marks, feedback |
| Result | attempt\_id, total\_marks\_awarded, max\_marks, percentage, published\_at |

# **10\. Essential Technical/UX Requirements**

* Responsive web application; student test/photo flow must work well on mobile browser.  
* Server-side role authorization for every protected API.  
* Autosave student answers and teacher evaluation entries.  
* Use durable object/file storage for answer images and keep only metadata/paths in database.  
* Uploaded solution photos must support preview and teacher zoom.  
* Protect student files from public unrestricted access; use authenticated/private access or signed URLs.  
* Do not allow question edits to change a student's already-submitted historical test content.  
* Show clear status for Generate, Upload, Save, Submit and Publish operations.  
* Prevent duplicate final submissions and duplicate result publication.  
* Basic backup of database and uploaded answer images is required for pilot data.

# **11\. Suggested Development Tasks / Build Order**

| Stage | Implementation tasks | Completion condition |
| :---- | :---- | :---- |
| 1\. Foundation | Authentication, roles, User model, Teacher/Student dashboards | Both roles log in and see correct empty dashboard. |
| 2\. Test & Question Models | Question, generation batch, test, assignment data structures | Teacher can create a draft test record. |
| 3\. AI Generation | Configuration UI, source retrieval, CBSE-style generation, random/twist logic | Teacher receives valid draft questions. |
| 4\. Review/Publish | Question review/edit/regenerate/approve and publish/assign | Approved test appears to assigned student. |
| 5\. Student Test | Attempt flow, MCQ, text answers, autosave, navigation | Student can answer and persist non-image questions. |
| 6\. Photo Answers | Camera/upload, multi-image, preview/replace, storage | Long-answer photos reach teacher in correct order. |
| 7\. Submission | Final confirmation, locking, teacher queue | Submitted attempt is immutable to student and visible to teacher. |
| 8\. Manual Evaluation | Answer viewer, image zoom, Correct/Wrong/Partial, marks, feedback | Teacher can fully mark an attempt. |
| 9\. Results | Total calculation, publish, student result page/history | Student sees published result. |
| 10\. Pilot Hardening | Permissions, error handling, upload limits, autosave/retry, responsive QA | End-to-end pilot is stable for real users. |

# **12\. Pilot Acceptance Test**

**☐** A teacher can log in.

**☐** A student can log in.

**☐** Teacher dashboard shows test/submission/evaluation counts.

**☐** Student dashboard shows available/completed tests.

**☐** Teacher can configure MCQ, mark-based and case-study question counts.

**☐** AI generates syllabus-grounded, CBSE-style questions.

**☐** Regeneration produces a meaningfully different question, not only different numbers.

**☐** Teacher can edit/regenerate/approve questions.

**☐** Teacher can publish an approved test to a student.

**☐** Student can select an MCQ answer.

**☐** Student can type a short answer.

**☐** Student can upload multiple notebook photos for a long answer and preview them.

**☐** Student can submit the test once.

**☐** Teacher can view every answer and zoom handwritten images.

**☐** Teacher can mark Correct/Wrong/Partial and enter manual marks.

**☐** System calculates total from teacher-entered marks.

**☐** Teacher can publish result.

**☐** Student can view total and question-wise result for that test.

# **13\. Pilot MVP Completion Definition**

| Definition of Done: The Pilot MVP is complete when one real teacher can create a CBSE-style Mathematics test from configured question types, approve and publish it; one or more real students can complete it using MCQ/text/handwritten-photo answers; the teacher can manually correct every submission; and each student can see the teacher-published result without any manual database intervention. |
| :---- |

