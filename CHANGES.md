# Etmam — Change Log

## Project Status Simplified
- Removed `draft`, `submitted`, and `approved` statuses from the Project model — they were unnecessary bureaucracy for a uni project system
- Only three statuses remain: **Active**, **Completed**, **Rejected**
- New projects now default to `active` instead of `draft`
- Assigning/removing a supervisor no longer changes the project status
- Filter dropdown, badge colours, and status edit select in the admin dashboard updated accordingly

## Admin — Gender Enforcement for Team Members
- When an admin searches for a student to add to an existing team, the search is now filtered to only return students whose gender matches the team's existing members (wrong-gender students are hidden entirely from results)
- Server-side guard added in `admin_add_member`: if the student's gender doesn't match the team's gender, the add is rejected with a clear error message (e.g. "Cannot add John: this is a female team")
- Teams with no members yet have no gender restriction — the first member added sets the gender

## Supervisor Pages Removed
- The standalone "Browse Supervisors" list page and individual supervisor detail page have been deleted. All supervisor browsing and requesting now happens entirely within the student dashboard.
- After sending a supervision request (or any related error), the student is redirected back to the student dashboard instead of the old detail page.

## Student Dashboard — Supervisor Tab
- Supervisor cards are now expandable. Clicking a card reveals the supervisor's expertise tags, bio, previous projects, and office hours. Only one card can be open at a time.
- The separate supervisor detail page is no longer needed (all info is shown inline on the card).

## Add User Page
- All fields are now mandatory (username, full name, email, role, gender, department, ID, password)
- A confirm password field was added with a live match indicator
- The Supervisor / Reviewer Settings section now has two separate fields: Max Teams Supervise and Max Teams Review, replacing the old single Max Teams field
- The role dropdown no longer has separate Supervisor and Reviewer options — they are combined into a single Supervisor/Reviewer option
