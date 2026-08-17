# Multipurpose Bot - Database Core Schema
The schema is designed to be scalable early on. A lot of work went into it :3

## Core Logic
There's 2 major object that we care about. **Staffs** and **Departments**. Staffs run a department, that has a Head. Each staff can be in multiple departments, and each department can handle a lot of staffs. There is 1 Head for every department (no support for co-heads at this moment).

Each department has auxiliary records for the service itself, and the application can associate assets (auxiliary records) to either the department of a staff.

In the future, there is a plan to expand the application for the whole playerbase. Minor additions must be added to `staff_staff` if need be, but i think it can handle it.

## 1. Core Entities (vibedocumented)
 
### 1.1 Staff (`staff_staff`)
- Identified by `staff_id` (PK), `name`, `discord_id` (unique).
- `title`, `timezone`, `schedule` (JSON, structure undefined) are optional metadata.
- `is_active`: `1` = has at least one active department membership, `0` = former staff (no active memberships).
- `is_blacklisted` (bool).
- `staff_id = 0` ("isaac") is the **Founder**, seeded and permanent.
 
### 1.2 Department (`staff_department`)
- Identified by `key` (PK), e.g. `bod`, `dept`, `dev`, `ad`, `cr`, `sys`, `qa`, `cont`, `inst`.
- Exactly one `head` (FK → staff). If a department currently has no assigned head, it defaults to staff 0 (Founder).
- `bod`'s own `head` is permanently staff 0 — not reassignable.
- `dept`'s `head` must be chosen from among current BOD members (see §3.2).
- `staff_level` — a fixed rank per department, only ever changed via migration (departments aren't created/removed through the app):
 
  | key | name | staff_level |
  |---|---|---|
  | bod | Board of Directors | 1 |
  | dept | Department Heads | 2 |
  | dev | Development | 3 |
  | ad | Administration | 4 |
  | cr | Community Relations | 5 |
  | sys | Systems | 6 |
  | qa | Testing Team | 7 |
  | cont | Contributors | 9 |
  | inst | Instruction | 10 |
 
- `configuration`, `servers` — opaque JSON, structure undefined by schema.
 
### 1.3 Membership (`staff_staff_department`)
- Many-to-many join of staff ↔ department, with its own `is_active` flag (per-department status).
 
### 1.4 Auxiliary records
- `staff_notes`, `staff_strikes` (has `department`, `strike_end`), `asset_tags` (unique `name`) + `staff_tags` (staff ↔ tag, unique pair).
- `department_tester_reports`, `department_instructor_instructions`, `department_tester_misc_performance` — QA/Instruction workflow tables. Their association to `qa` / `inst` is enforced at the app level, not via a `department_key` FK.
 
## 2. Roles & Authority
 
| Actor | Scope |
|---|---|
| **Founder** (staff 0) | Only one who can assign `bod` membership |
| **BOD member** | Assigns department heads; can hire/fire/strike/edit *any* staff regardless of department |
| **Department head** | Can hire, fire, strike, and edit staff who hold any active membership in a department they head — even if that staff also belongs to other departments |
| **Sys-empowered head** | Anyone who is *both* an active `sys` member *and* an active head of some department gets Founder-equivalent power |
| **Regular staff** | No administrative authority |
 
## 3. Business Rules
 
### 3.1 Automatic department membership
- Anyone who is `head` of **any** department is auto-added (active) to `dept` (Department Heads).
- Anyone who is `head` of a department with `staff_level` 1–4 (`bod`, `dept`, `dev`, `ad`) is auto-added (active) to `bod`.
- In practice this rarely triggers new membership for `dept`'s own head, since that head must already be a BOD member before being assigned (§3.2).
 
### 3.2 Assignment authority
 
| Action | Who |
|---|---|
| Add/remove `bod` membership | Founder only |
| Set/change a department's `head` | BOD only. Candidate for `dept` head must already be a BOD member. Setting a head both updates `staff_department.head` and grants that department's membership if not already held. |
| Hire / fire staff (add/remove dept membership) | BOD (any dept); Dept head (own dept only) |
| Add strike / note | Same scope as hire/fire |
| Assign tag | Same scope as hire/fire |
| Remove tag / note / strike | Only the original assigner, or BOD |
| Modify a department's `configuration` / `servers` | That department's head, or BOD |
| Modify `staff_level` | BOD only (via migration) |
| Override a blacklist | BOD only |
| Any of the above | Sys-empowered head acts as Founder |
 
### 3.3 Lifecycle
- Staff with **no active department memberships** → `is_active = 0`, tagged `"Former Staff"`.
- Staff can only be blacklisted if they are already former staff (`is_active = 0`); blacklist is a superset of former-staff status — a blacklisted staff keeps `"Former Staff"` and gains `"Blacklisted"`.
- Marking `is_blacklisted` deactivates all remaining department memberships and adds the `"Blacklisted"` tag.
- 3 strikes → auto-fire (memberships deactivated) → auto-blacklist. This blacklist is **permanent**: it is not reversed even if the underlying strikes later expire (`strike_end` passes).
- Only BOD can lift a blacklist.


## 4. Auxiliary Tables
### 4.1. Development Department (Bug Logger) Tables
Tables that involve the Bug Logger are `department_tester_reports` and `department_tester_misc_performance` (currently unused). 
The main working object of Bug Logger are Bugs. It is posted on a bug reports channel, it can be marked as fixed/not fixed, it can be triaged, and be assigned to a specific Developer to be fixed (not tightly enforced)

Testers can also be noted for other thing they do outside of posting bug reports (specified thru the `department_tester_misc_performance.mode` column)

### 4.2. Staffpanelicious-specific Tables
A staff can be additionaly managed thru Staffpanelicious. They can have a note (contents to the discretion of the head), be striked by their head, have tags (i.e. on LOA).