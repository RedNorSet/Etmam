# Etmam — Development Changes Reference

Complete log of every intentional change made to the codebase. Organized by area.

---

## Authentication & Accounts

- **Password strength enforcement** — Creating or resetting a password requires ≥ 8 characters, at least one letter, and at least one number. A live strength bar and rule checklist are shown in the form.
- **Gender locked after creation (active users)** — On the Edit User page, gender is displayed as a disabled read-only field for active users and is never saved by the edit form.
- **Gender editable for inactive (archive) users** — When `target.is_active == False`, the gender field becomes an editable `<select>` on the Edit User page. The view saves gender only in that case.
- **Department dropdown** — The department field in Add User and Edit User forms is a dropdown with 10 fixed CS departments instead of a free-text input.
- **Required fields on edit** — Saving an edit with an empty username, full name, email, or department is blocked both client-side and server-side with a clear error.

---

## Admin: User Management

- **Delete user button** — Each user row in the admin Users panel has a red "Delete" button that opens a confirmation modal. An admin cannot delete their own account.
- **Department filter bubbles** — All three user tables (Students, Staff, Admins) have a scrollable row of department filter pills below the gender filter.
- **Inactive students sorted to bottom** — The Students table orders active accounts first, then `is_active=False` accounts last, via a `Case/When` annotation in `admin_dashboard`.
- **Supervising / Reviewing columns** — The single "Teams" column in the Supervisors & Reviewers table was split into two: "Supervising" (`current_load / max_teams_supervise`) and "Reviewing" (`current_review_load / max_teams_review`).

---

## Admin: Teams & Projects

- **Department column** — A "Dept" column shows the team's department in the accordion table.
- **Department filter dropdown** — A department filter dropdown in the filter bar is now correctly linked: option values are lowercase to match the `|lower`-filtered `data-dept` attribute on each row.
- **Teams `data-dept` lowercased** — `data-dept="{{ team_dept|lower }}"` ensures the JS filter comparison works regardless of how the department was stored.
- **Status filter updated** — The status dropdown lists all current statuses: In Progress, Active, Needs Review, Completed (Rejected removed from UI).
- **Completed projects excluded** — `raw_teams` is built with `.exclude(project__status='completed')`, so teams whose project is complete only appear in the Archive panel, never in Teams & Projects.

---

## Admin: Archive Panel

- **Archive tab** — A dedicated "Archive" nav panel lists all completed projects with collapsible cards.
- **Show/Hide visibility toggle** — Each project card has a Show/Hide button that controls `hide_from_archive`, used to keep a project out of the student/supervisor archive view.
- **Auto-populated** — Any project whose status transitions to `completed` automatically appears here.
- **Expanded card displays** — Supervisor name + email + department; each member's name, role badge, and email.
- **Final submitted files** — Download links for the last submission against milestone order=5 are shown in the expanded card.
- **Edit project info** — Title, description, status, and supervisor are all editable from an inline form inside the card. Posts to `admin_update_project` with `source=archive` and redirects back to the Archive panel.
- **Edit members inline** — Each member row has a ✎ Edit button that expands an inline form to update their `full_name` and `email` (updates the User record directly).
- **Set leader** — Each non-leader member row has a 👑 Set Leader button. Demotes the current leader to member and promotes the selected one. POST to `admin_archive_set_leader(member_id)`.
- **Add member (name + email)** — The ＋ Add Member form accepts Full Name + Email and creates an inactive placeholder user via `_make_archive_user()`. Alternatively, filling the optional "existing username" field links to an existing student account.
- **Remove member** — ✕ Remove button with confirmation dialog deletes the `TeamMember` record; the User account is preserved.
- **Project links** — Admin can add custom URL links (label + URL) to any archive entry (e.g. GitHub repo, demo video). Each link is displayed and can be individually deleted. Stored in the `ArchiveLink` model (`projects` app, migration `0008_archive_link`).
- **Delete archive entry** — A red "Delete This Archive Entry" button (with `confirm()` dialog) permanently deletes the project and its team. User accounts for members are preserved.
- **Full "Add Historical Project" form** — The creation form includes supervisor dropdown, dynamic member rows (Full Name + Email, ＋ Add Member / ✕ remove per row), and dynamic link rows (Label + URL), all submitted in one POST.
- **`Inactive<N>` username format** — `_make_archive_user()` assigns the lowest-available gap-filling username: `Inactive1`, `Inactive2`, … Deleting `Inactive2` then adding a new member assigns `Inactive2` again.

---

## Admin: Project Status System

- **New status values** — `Project.STATUS` has 5 choices: `in_progress`, `active`, `needs_review`, `completed`, `rejected`. Migration `0009_phase2_start_date` alters the field.
- **Auto-recalculate on every admin dashboard load** — `_refresh_project_statuses()` runs at the start of each `admin_dashboard` request and bulk-updates all non-completed projects:
  - Phase 1, any state → `in_progress`
  - Phase 2, last milestone due date not yet passed → `active`
  - Last milestone due date passed + any unsubmitted milestones → `needs_review`
  - Last milestone due date passed + all milestones submitted → `completed`
- **Completed projects never downgraded** — Once a project reaches `completed` it is skipped by the refresh, keeping it in the Archive permanently.
- **Students deactivated on completion** — When `_refresh_project_statuses()` transitions a project to `completed`, all active student members of that team have `is_active` set to `False` automatically.
- **Previously-rejected projects auto-corrected** — The refresh no longer excludes `rejected` projects; on the next admin page load they are recomputed to their correct status.
- **`rejected` removed from UI** — The Rejected option was removed from the Teams accordion project-edit form, the Archive project-edit form, and the Teams status filter dropdown.

---

## Admin: Phase 2 Scheduling

- **`phase2_start_date` field on `SystemConfig`** — New nullable `DateField` (migration `0009`). Editable from the System panel via a date picker form.
- **Auto-trigger on date** — On each admin dashboard load, if `phase == 1` and `phase2_start_date ≤ today`, the full Phase 2 switch runs automatically and a ⚡ success banner is shown.
- **Refactored switch logic** — `_execute_phase2_switch(admin_user)` is a standalone helper that returns a stats dict. Both the manual "Switch to Phase 2" button and the auto-trigger use it — no duplicated logic.
- **Revert clears the date** — `admin_revert_phase1` clears `phase2_start_date` so the auto-trigger does not re-fire after a deliberate revert.

---

## Admin: Phase 2 Auto-Assignment

- **Pending invites cancelled first** — ALL pending team invites are deleted before any grouping/assignment (prevents stale invites and the prior `IntegrityError` crash).
- **Fill existing teams to 5** — Manually-created teams with fewer than 5 members are topped up from the teamless pool (same gender + department).
- **Create auto-teams of 5** — Remaining teamless students form teams of 5 (or 4 if that's all that's left in the bucket).
- **Distribute < 4 leftovers** — Fewer than 4 remaining students are distributed one-per-team to existing 5-member teams in the same bucket (max 6 per team).
- **Auto-assign supervisors (round-robin)** — Projects without a supervisor get one assigned round-robin per gender bucket.
- **Auto-assign exactly 2 reviewers** — Adds 2 reviewers if none exist, adds 1 if only 1, skips if already 2+. Supervisor excluded from reviewer pool.

---

## Admin: Grades

- **Single "Save All Grades" button** — The duplicate button at the top of the grade sheet was removed.
- **Pending Grades count fixed** — The badge now counts only milestone slots that have an actual student submission with no admin grade yet. Previously it counted every possible grade slot regardless of whether a submission existed.
- **Grade validation message** — When `admin_save_all_grades` skips an out-of-range value, the message now explicitly says "grades must be between 0 and 100". Inputs already have `min="0" max="100"` attributes.
- **Milestone weight reminder** — After creating a new milestone, if the total weight of all active milestones is not 100%, a warning banner tells the admin to adjust weights in the Grades panel.

---

## Admin: Supervisor Assignment

- **Capacity check crash fixed** — `admin_assign_supervisor` previously crashed with `NameError` when `max_teams_supervise != 1` (Django template filter `|pluralize` was used inside a Python f-string). Fixed to plain Python string logic. The capacity block now correctly prevents over-limit assignments.

---

## Admin: Overview

- **"Missed Milestones" stat** — Counts milestones past their due date **with no submission**, not just past-due milestones.

---

## Milestones

- **Guide document upload** — Each milestone has an optional `guide_file` field. Admins upload when creating or editing. Students see a "Download Milestone Guide" link in their milestone detail panel.

---

## Student: Milestones & Submissions

- **Block submission after due date** — `student_submit_milestone` checks `milestone.due_date`; if today is past it, the submission is rejected with a clear error.
- **Task description displayed** — Each task item shows its description below the title for all team members.
- **Task description field in creation form** — The "Add task" form includes an optional description textarea (leader-only).
- **Leader can edit existing task descriptions** — A ✎ button per task opens an inline edit form (leader-only).
- **"Assign to" dropdown styled** — The task creation select now has `background:#1e293b; color:#f1f5f9` with matching option styling, making it clearly readable in the dark milestone panel.

---

## Student: Team

- **Invite gated by phase and role** — The invite member form is only visible to the team leader in Phase 1. In Phase 2 or for non-leaders it is hidden.

---

## Student: Supervisors Section

- **Phase 1** — Shows a browsable grid of available supervisors with request buttons.
- **Phase 2** — Replaces the grid with collapsible profile cards showing the team's assigned supervisor and assigned reviewers. No request functionality shown.

---

## Student: Profile Edit

- **Profile page** — Route `GET/POST /dashboard/student/profile/` (`dashboard:student_edit_profile`). Accessible via "✏️ Edit Profile" in the sidebar bottom (above Sign Out), matching the supervisor's sidebar layout.
- **Interface matches supervisor profile** — Standalone HTML page (not extending base.html), same gradient profile header, same card-based layout, same topbar with ← Dashboard breadcrumb.
- **Editable: Bio / description** — Saved with `action=bio`; updates `user.bio`.
- **Editable: Password** — In-page form (`action=password`): verifies current password, enforces 8-char + letter + digit rule with live color-coded checklist, uses `update_session_auth_hash` to keep the session valid after change.
- **Read-only info** — Full name, username, email, student ID, department, gender shown but not editable. Note directs students to admin for those fields.

---

## Supervisor: Profile

- **Edit Profile link in sidebar bottom** — "✏️ Edit Profile" link in `sidebar-bottom` above Sign Out, linking to `accounts:supervisor_profile`.

---

## Supervisor: Meetings — Participant Picker

- **Grouped by team** — Participants shown grouped under their team name and project title.
- **Select-all per team** — A team-header checkbox selects/deselects all members of that team.

---

## Reviewer Grading

- **`ReviewerGrade` model** — Stores one grade + feedback per reviewer per submission (per component for split milestones).
- **Final grade formula** — `sub.grade = (supervisor_grade + all_reviewer_grades) ÷ total_graders`. Equally weighted.
- **Reviewer sees own grade pre-filled** — Previously submitted values are shown when reopening the grading panel.

---

## Submission Grades → Admin Grade Sheet (Auto-Sync)

- **Auto-populate from supervisor/reviewer grading** — After any supervisor or reviewer submits a grade, `sub.grade` is written to the matching `ProjectGrade` cell automatically.
- **Grading removed from Submissions panel** — The duplicate grade inputs were removed; grading is done exclusively from the My Teams section (split-aware).

---

## Component-Aware Grading (Split Milestones)

- **Split grading UI** — When a milestone has report/presentation split configured, supervisors and reviewers see separate "Report %" and "Presentation %" inputs.
- **Per-component averaging** — Each component is averaged independently across all graders; weighted sum gives `sub.grade`.
- **Auto-sync both components** — Both component averages are written to `ProjectGrade` automatically.
- **Data model** — `supervisor_report_grade` + `supervisor_presentation_grade` on `Submission`; `component` field on `ReviewerGrade`.

---

## Project Edit Workflow (Leader → Supervisor Approval)

- **Leader proposes edits** — Team leader sees a collapsible form in Milestones to propose a new title/description.
- **Supervisor approves or rejects** — Supervisor sees a pending-edit card with current vs. proposed values and Approve/Reject buttons.
- **Reject reverts to original** — Deletion of the pending request; original values preserved.
- **Notifications both ways** — Proposing notifies the supervisor; approving/rejecting notifies the leader.

---

## Navigation (Stay on Same Page)

- **Hash-based section routing** — Student and supervisor dashboards detect `window.location.hash` on load and jump to the correct section.
- **Action redirects carry hash anchors** — Team actions → `#sec-team`, milestones/tasks/submissions → `#sec-milestones`, supervisor requests → `#sec-supervisors`, grading → `#sec-submissions`.

---

## Supervision & Review Limits

- **Supervision limit enforced** — Admin assigning a supervisor who has reached `max_teams_supervise` is blocked with an error. Supervisor accepting a request that exceeds the limit is also blocked.
- **Review limit enforced** — Admin assigning a reviewer who has reached `max_teams_review` is blocked.
- **Supervisor listing filtered by department** — On the student dashboard, available supervisors are filtered by the student's department.
- **Supervision request validates department** — `request_supervision` checks department match.
