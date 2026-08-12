
# STUDENT ENGAGEMENT MONITORING PROJECT
# COMPLETE CLASS HISTORY + ATTENDANCE IMPLEMENTATION

You are working on my existing Student Engagement Monitoring project.

I am providing you with:
1. The complete project structure.
2. Important frontend source files.
3. Important backend source files.
4. Existing AI monitoring, class scheduling, login, WebSocket and dashboard code.

IMPORTANT:
Do NOT redesign the application.
Do NOT remove working functionality.
Do NOT replace working AI monitoring.
Do NOT create dummy/random data.
Do NOT make isolated changes in only one file.

First understand the existing architecture and data flow completely.
Then implement the requirements below by making coordinated changes across
the necessary frontend and backend files.

After making changes:
- Tell me every file that was changed.
- Explain what was changed in each file.
- Give the complete final code for every changed file.
- Make sure imports, types, API routes, WebSockets and frontend queries all remain consistent.
- Make sure the project builds and runs without TypeScript/Python errors.
- Do not leave duplicate functions, duplicate variables or unused imports.

============================================================
PART 1 — CLASS LIFECYCLE
============================================================

The existing application already allows the teacher to create/schedule/start/end
classes.

Preserve this existing functionality.

The required lifecycle is:

TEACHER CREATES/SCHEDULES CLASS
        ↓
CLASS EXISTS WITH A UNIQUE classId
        ↓
TEACHER STARTS CLASS
        ↓
CLASS STATUS = LIVE
        ↓
STUDENTS CAN JOIN THAT SPECIFIC CLASS
        ↓
AI MONITORING RUNS DURING THAT CLASS
        ↓
MONITORING DATA IS STORED AGAINST:
        classId + studentId
        ↓
TEACHER ENDS CLASS
        ↓
CLASS STATUS = COMPLETED
        ↓
MONITORING SESSION IS FINALIZED
        ↓
HISTORICAL DATA IS AVAILABLE
FOR BOTH TEACHER AND STUDENT

A class must have one unique ID that is used everywhere.

Do not identify historical data only by student name.

Use:

classId
studentId

as the primary relationship.

============================================================
PART 2 — STUDENT JOINING A CLASS
============================================================

When a student joins a teacher's live class:

Create/associate a monitoring session:

classId
studentId
studentName
joinTime

The student must be associated with the exact class they joined.

Do not mix monitoring data from different classes.

If the same student attends two different classes, those must become
two separate historical sessions.

Example:

Class A
  └── Student Disha
       └── monitoring history for Class A

Class B
  └── Student Disha
       └── completely separate monitoring history for Class B

============================================================
PART 3 — REAL AI MONITORING DATA
============================================================

During the live class, the existing AI monitoring system already produces
real-time information.

Do not replace this AI system.

Persist the real monitoring results for each student.

For every monitoring snapshot, store as much of the existing real AI data
as the current system provides, including:

- studentId
- studentName
- classId
- timestamp
- engagement score
- emotion
- cognitive state
- gaze direction
- head pose
- blink count
- phone detection
- person count
- active alert
- engagement status
- authentication status
- any other existing AI monitoring fields already available

Do not invent values.

Do not use random/mock values for historical class records.

The data should be associated with the actual student and actual class.

============================================================
PART 4 — MONITORING HISTORY
============================================================

For each student in a class, maintain a chronological monitoring history.

Example:

Class: Machine Learning
Class ID: class-123

Students:
  Disha
    10:01 → engagement 82, phone false, gaze center
    10:02 → engagement 79, phone false, gaze center
    10:03 → engagement 42, phone true, gaze center
    10:04 → engagement 38, phone true, gaze away
    ...

  Rohan
    10:01 → engagement 91
    10:02 → engagement 88
    ...

When the teacher ends the class, this history must be preserved.

Do NOT delete it after ending the class.

============================================================
PART 5 — TEACHER DASHBOARD
============================================================

After a class ends, the teacher must be able to access the historical
class information.

Teacher dashboard/history should work conceptually like:

TEACHER
  ↓
COMPLETED CLASSES
  ↓
SELECT A CLASS
  ↓
SHOW STUDENTS WHO JOINED THAT CLASS
  ↓
SELECT A STUDENT
  ↓
SHOW THAT STUDENT'S COMPLETE CLASS HISTORY

When the teacher opens a completed class, display:

- Class name
- Subject
- Date
- Start time
- End time
- Number of students who joined
- Students who joined

Each student should be displayed by their real student name.

Example:

Machine Learning
Completed

Students:
  Disha Sharma
  Rohan Verma
  Aarav Mehta

Click:

Disha Sharma

Then show Disha's data for THIS CLASS ONLY.

============================================================
PART 6 — STUDENT DETAIL VIEW FOR TEACHER
============================================================

When the teacher clicks a student inside a completed class, show:

Student:
Disha Sharma

Class:
Machine Learning

Class duration:
10:00 - 10:50

Monitoring summary:

- Average engagement
- Final engagement
- Minimum engagement
- Maximum engagement
- Number of monitoring samples
- Emotion information
- Blink count / blink history if available
- Gaze information
- Head pose information
- Phone detection occurrences
- Multiple-person occurrences
- Alerts generated
- Cognitive state
- Authentication status
- Timeline/history of monitoring values

The teacher should be able to understand what happened during the class.

If the current application already has charts/components for engagement,
reuse them instead of creating unnecessary new UI components.

============================================================
PART 7 — STUDENT DASHBOARD
============================================================

The same completed-class monitoring data must also be available to the
student, but with restricted visibility.

A student must ONLY be able to see their own monitoring data.

A student must NOT be able to see:

- Other students' names
- Other students' engagement
- Other students' phone detection
- Other students' alerts
- Other students' monitoring history

Student view:

STUDENT
  ↓
MY COMPLETED CLASSES
  ↓
SELECT CLASS
  ↓
MY MONITORING SUMMARY

Show:

- Class name
- Subject
- Date
- Start/end time
- Average engagement
- Final engagement
- Engagement history
- Emotion
- Blink count
- Gaze
- Head pose
- Phone detection
- Person count
- Alerts
- Cognitive state
- Any other monitoring data belonging to that student

============================================================
PART 8 — DATA PERSISTENCE
============================================================

The data must not exist only in React component state.

Do not depend on:

useState()
useRef()
temporary arrays
temporary in-memory variables

for the final historical data.

Use the application's existing persistence architecture.

If the current project is using a backend/database:
store the historical class monitoring data in the backend/database.

If the current project is currently in mock/demo mode:
implement the persistence in the existing mock/storage architecture without
breaking the future backend architecture.

The most important requirement is:

Teacher and student must read the SAME historical class/session data.

Do not create:

Teacher monitoring history

and separately:

Student monitoring history

with duplicated independent data.

There should be one source of truth.

Conceptually:

ClassMonitoringSession
    classId
    className
    startTime
    endTime
    status
    students[]

StudentMonitoringSession
    classId
    studentId
    studentName
    joinTime
    leaveTime
    snapshots[]

Snapshots:
    timestamp
    engagement
    emotion
    gaze
    headPose
    blinkCount
    phoneDetected
    personCount
    cognitiveState
    alert
    ...

============================================================
PART 9 — TEACHER ENDS CLASS
============================================================

When the teacher clicks "End class":

1. Stop the live class.
2. Stop/finalize the monitoring session.
3. Save the final monitoring snapshot for every connected student.
4. Calculate summary information for every student.
5. Save the class as COMPLETED.
6. Preserve the complete monitoring history.
7. Make the completed class available in teacher history.
8. Make the completed class available in the student's own history.

Do NOT delete the monitoring session after the class ends.

============================================================
PART 10 — ATTENDANCE
============================================================

Attendance is separate from live monitoring.

DO NOT award attendance when the student joins.

DO NOT award attendance while the class is running.

Attendance must be finalized ONLY when the teacher ends the class.

Attendance rule:

A student receives PRESENT attendance only if:

1. The student actually joined the class.
2. The student's monitoring session contains engagement samples.
3. The student's average engagement throughout the entire session is MORE
   THAN 50%.
4. The student's engagement at the end/latest valid monitoring point is MORE
   THAN 50%.

Both conditions must be satisfied.

Example:

Average = 72%
Final engagement = 68%

→ PRESENT

Example:

Average = 72%
Final engagement = 43%

→ NOT PRESENT

Example:

Average = 48%
Final engagement = 70%

→ NOT PRESENT

Example:

Average = 48%
Final engagement = 43%

→ NOT PRESENT

Use strictly:

averageEngagement > 50
AND
latestEngagement > 50

Attendance is created only after the teacher ends the class.

============================================================
PART 11 — NO RANDOM DATA
============================================================

Remove/avoid random generated data for:

- Attendance
- Completed class monitoring history
- Student historical monitoring
- Teacher historical student records

Do not show fake students in a completed class.

Do not show fake attendance.

Do not show fake monitoring history.

If there is no real data, show an appropriate empty state.

For example:

"No completed classes yet."

"No students attended this class."

"No monitoring data available."

============================================================
PART 12 — CLASS LISTS
============================================================

Student dashboard should NOT contain random predefined classes.

Only show classes that are actually created/scheduled by the teacher.

Expected:

Teacher schedules class
    ↓
Student can see scheduled class

Teacher starts class
    ↓
Student can join live class

Teacher ends class
    ↓
Class becomes completed/history
    ↓
Historical monitoring data becomes available

Do not restore the old dummy classes.

============================================================
PART 13 — API / BACKEND
============================================================

Inspect the existing backend carefully.

If the backend already has:

- FastAPI
- WebSocket signaling
- AI monitoring endpoints
- class routes
- monitoring routes

reuse them.

Do not create duplicate APIs if an existing endpoint can be extended.

Create appropriate APIs only when necessary.

Potential logical operations are:

GET class history
GET completed classes
GET students for a class
GET monitoring history for student + class
GET student's own class history
POST/record monitoring snapshot
POST/finalize class
POST/finalize attendance

But use the project's existing API conventions.

Do not blindly create these exact endpoints if equivalent existing endpoints
already exist.

============================================================
PART 14 — WEBSOCKET
============================================================

The existing WebSocket/WebRTC system is already working.

Do not break:

- student camera
- teacher camera
- WebRTC signaling
- AI result messages
- phone detection notifications
- multiple-person notifications
- looking-away notifications

Extend the existing AI-result flow so that real monitoring results are
persisted against:

classId
studentId

The WebSocket should continue doing its current live-monitoring job.

Persistence should happen in addition to live display.

============================================================
PART 15 — FRONTEND DATA FLOW
============================================================

Make sure the frontend does NOT rely on stale cached data after the teacher
ends a class.

Invalidate/refetch the appropriate React Query keys.

For example, after class completion:

- classes
- completed classes
- class history
- monitoring history
- student history
- attendance

should be refreshed as appropriate.

Use the project's existing React Query architecture.

============================================================
PART 16 — SECURITY / STUDENT VISIBILITY
============================================================

Teacher:
Can see all students belonging to their class.

Student:
Can see ONLY their own historical monitoring data.

Do not expose another student's data to the student dashboard.

Use the authenticated student ID rather than trusting a student-selected ID
from the frontend.

============================================================
PART 17 — UI REQUIREMENTS
============================================================

Do not redesign the existing UI.

Preserve the current:

- sidebar
- teacher navigation
- student navigation
- dashboard styling
- cards
- typography
- colors
- components

Add the required history/detail functionality using the existing design
system.

============================================================
PART 18 — IMPLEMENTATION ORDER
============================================================

Implement in this order:

1. Understand existing architecture.
2. Identify current class lifecycle.
3. Identify current student join flow.
4. Identify current AI-result flow.
5. Identify current persistence/storage.
6. Create/extend class monitoring session storage.
7. Store monitoring snapshots by classId + studentId.
8. Finalize monitoring when teacher ends class.
9. Build teacher completed-class → students → student-details flow.
10. Build student completed-class → own-details flow.
11. Implement attendance finalization at class end.
12. Remove remaining random historical attendance/class data.
13. Verify React Query refresh/invalidation.
14. Verify TypeScript/Python/build errors.
15. Verify no duplicate functions or conflicting stores.

============================================================
PART 19 — TEST CASES
============================================================

After implementation, verify these cases:

TEST 1:
Teacher creates class.
Student dashboard sees it.

TEST 2:
Teacher starts class.
Student joins.

TEST 3:
Student generates real AI monitoring data.

Verify that the teacher receives:

- engagement
- emotion
- gaze
- head pose
- phone detection
- person count
- alerts
- etc.

TEST 4:
During class, monitoring history is being stored against:

classId + studentId.

TEST 5:
Teacher ends class.

Verify class status becomes completed.

TEST 6:
Open Teacher → Completed Class.

Verify the student who joined is shown by name.

TEST 7:
Click the student.

Verify the student's complete monitoring history for THAT class is shown.

TEST 8:
Open Student → Completed Classes.

Verify the same class appears.

TEST 9:
Open the completed class as the student.

Verify ONLY that student's own monitoring information is shown.

TEST 10:
Attendance:

Average > 50 AND latest > 50
→ PRESENT

Average <= 50 OR latest <= 50
→ NOT PRESENT

TEST 11:
End class with no student.

Verify:
No fake student.
No fake attendance.
No fake monitoring history.

TEST 12:
Restart/reload the application.

Verify completed class history is still available.

============================================================
FINAL REQUIREMENT
============================================================

Do not just tell me how to implement this.

IMPLEMENT IT IN THE PROVIDED PROJECT.

Inspect all relevant existing files first.

Make all required coordinated changes.

Do not give partial pseudo-code.

Do not leave TODOs such as:

// implement later
// connect backend later
// add database later

The final result must be a working implementation using the existing
project architecture.

After implementation, provide:

1. List of files changed.
2. What changed in each file.
3. Any new API/storage structures.
4. How class → student → monitoring history works.
5. How teacher sees the data.
6. How student sees the data.
7. How attendance is calculated.
8. Exact commands to run the frontend and backend.
9. Any migration/setup steps required.
10. A short testing checklist.

MOST IMPORTANT:

Do not destroy or replace functionality that is already working.
Modify the existing project intelligently and minimally.
