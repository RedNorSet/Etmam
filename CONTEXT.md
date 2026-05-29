# Etmam — Project Context

## Overview
**Etmam** is a Graduation Project Management System (GPMS) built with Django 5.2 + PostgreSQL.
It manages the full lifecycle of student graduation projects: team formation, supervisor assignment, milestone tracking, task management, submissions, grading, and archiving.

- **Repo:** https://github.com/RedNorSet/etmam.git
- **Current branch/version:** `etmam_V0.6`
- **Stack:** Django 5.2, PostgreSQL, vanilla JS (SPA-style dashboard, no framework), Windows 11 / PowerShell
- **Run:** `cd C:\Users\Yasir\Documents\programs\gpms_v3 && python manage.py runserver`
- **Seed data:** `python manage.py loaddata data_v0.6.json`

---

## User Roles
| Role | Description |
|------|-------------|
| `student` | Forms teams, requests supervisors, submits milestones, manages tasks |
| `supervisor` | Oversees assigned teams, grades submissions, attends meetings |
| `reviewer` | Reviews and grades submissions (no team assignment) |
| `administrator` | Full system control — users, phases, projects, archive |

---

## App Structure
```
accounts/       — User model (role, gender, department, student_id, max_teams, can_review)
core/           — Root URL conf
dashboard/      — Main SPA dashboards (student, supervisor, admin, archive)
meetings/       — Meeting scheduling between teams and supervisors
milestones/     — GlobalMilestone, Milestone, ProjectGrade, Task models
notifications/  — Notification model + mark-read views
projects/       — Project, SystemConfig models
reviews/        — Review model
submissions/    — Submission model + grading views
teams/          — Team, TeamMember models
```

---

## Key Models

### `accounts.User` (extends AbstractUser)
- `role` — student / supervisor / reviewer / administrator
- `gender` — male / female (enforced for team invites and supervisor requests)
- `full_name`, `student_id`, `department`
- `max_teams`, `available`, `can_review`

### `projects.Project`
- `title`, `description`, `status` (active / completed / rejected)
- `team`, `supervisor`, `reviewers` (M2M)
- `hide_from_archive`, `auto_assigned_supervisor`

### `projects.SystemConfig` (singleton, pk=1)
- `phase` — 1 or 2
- `phase_switched_at`

### `milestones.Milestone` (GlobalMilestone instances per project)
- `title`, `weight`, `due_date`, `order`
- Related: `submissions.Submission`, `milestones.Task`

### `milestones.Task`
- `project`, `milestone`, `title`, `description`
- `assigned_to`, `created_by`
- `due_date`, `status` (todo / in_progress / done)

### `submissions.Submission`
- `project`, `milestone`, `file`, `status` (pending / submitted / approved / revision)
- `supervisor_grade`, `supervisor_feedback`, `supervisor_graded_by/at`
- `reviewer_grade`, `reviewer_feedback`, `reviewer_graded_by/at`
- `grade` — auto-calculated composite `(supervisor + reviewer) / 2`

### `notifications.Notification`
- `recipient`, `type` (invite / meeting / approval / feedback / deadline / risk / general)
- `title`, `body`, `link`, `is_read`

---

## Dashboard Architecture
Single-page app — one HTML file per role, JS `showSection()` controls visibility. No page reloads between sections.

### Student sections
`dashboard` · `team` · `milestones` · `meetings` · `notifications` · `archive`

### Supervisor sections
`dashboard` · `teams` · `submissions` · `meetings` · `notifications`

### Admin sections
`dashboard` · `users` · `projects` · `grades` · `system`

---

## Phase System (Admin)
- **Phase 1** — Students form teams manually, request supervisors.
- **Switch to Phase 2** triggers:
  1. Auto-group teamless students by gender + department into teams of 5
  2. Create a project per auto-group
  3. Assign supervisors round-robin by gender (respects `max_teams`)
  4. Auto-assign reviewers randomly (skip own supervisor)
  5. Decline all pending supervision requests
- **Revert to Phase 1** (testing) — removes auto-created teams/projects/assignments, re-opens declined requests.

---

## Gender Rules
- Students can only invite same-gender + same-department teammates
- Students can only request same-gender supervisors
- Student search auto-filters by gender and department
- Enforced in `teams/views.py` and `projects/views.py`

---

## Notifications Behaviour
- Clicking Notifications nav or topbar bell → `markAllRead()` fires instantly (POST to `notifications:mark_all_read`, no page reload)
- Clicking a notification → `openNotif(type)` navigates to the relevant section via `showSection()`
- **Student mapping:** `invite→team`, `meeting→meetings`, `approval/feedback/deadline/risk/general→milestones`
- **Supervisor mapping:** `invite/approval/general→teams`, `meeting→meetings`, `feedback/deadline/risk→submissions`

---

## Milestones Section (Student)
Two-column split-pane:
- **Left list** — all milestones, status pill, deadline countdown, task progress bar
- **Right detail panel** — status banner, grade/feedback block, Tasks section (create/complete/delete), Submission form

---

## Key URLs
```
/dashboard/student/         — student dashboard
/dashboard/supervisor/      — supervisor dashboard
/dashboard/admin/           — admin dashboard
/dashboard/task/create/     — create task (POST)
/dashboard/task/<pk>/update/ — update task status (POST)
/dashboard/task/<pk>/delete/ — delete task (POST)
/submissions/grade/supervisor/<id>/ — supervisor grade (POST)
/submissions/grade/reviewer/<id>/   — reviewer grade (POST)
/notifications/<pk>/open/           — mark read + redirect
/notifications/mark-all-read/       — bulk mark read (POST, returns JSON)
```

---

## Setup for a New Developer
```bash
git clone https://github.com/RedNorSet/etmam.git
cd etmam
pip install -r requirements.txt
# configure .env with DATABASE_URL and SECRET_KEY
python manage.py migrate
python manage.py loaddata data_v0.6.json   # optional — loads 125 seed records
python manage.py runserver
```

---

## Version History
| Version | Key Changes |
|---------|-------------|
| v0.3 | Admin panel rework, M2M reviewers, dissolve undo, create team, notifications |
| v0.4 | Grading system, milestone splits, bug fixes |
| v0.5 | Phase system, Task model, gender rules, milestones redesign, notifications UX, grading implemented, archive |
| v0.6 | Project statuses simplified (active/completed/rejected), admin gender enforcement for team members, supervisor pages removed, add-user page rework |
