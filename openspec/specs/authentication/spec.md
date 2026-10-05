# Authentication Specification

## Purpose

User identity, session management, and the distinction between guest and authenticated modes.
Authentication is handled entirely by Supabase Auth.

---

## Requirements

### Requirement: Magic Link Authentication

The system SHALL support passwordless authentication via a magic link sent to a user's email address.

#### Scenario: Magic link sent

- GIVEN a user enters a valid email address and submits the sign-in form
- WHEN the system processes the request via Supabase Auth
- THEN a magic link email is dispatched to the user
- AND the user is shown a confirmation message to check their email

#### Scenario: User clicks magic link

- GIVEN the user clicks the link in the email
- WHEN Supabase Auth validates the token
- THEN a session is established and the user is redirected to the application in an authenticated state

---

### Requirement: Google OAuth Authentication

The system SHALL support authentication via Google OAuth.

#### Scenario: Successful Google sign-in

- GIVEN the user selects "Sign in with Google"
- WHEN the OAuth flow completes successfully
- THEN a session is established and the user is returned to the application in an authenticated state

---

### Requirement: Guest Mode

The system SHALL allow full use of core functionality without authentication.

#### Scenario: Guest can configure and generate a PDF

- GIVEN a user who has not signed in
- WHEN the user adds publications, configures an issue, and clicks "Generate PDF"
- THEN the PDF is generated and a download link is returned without requiring sign-in

#### Scenario: Guest configuration stored in localStorage

- GIVEN a guest user configures an issue
- WHEN the page is reloaded in the same browser
- THEN the previously configured issue (title, publications, format, frequency) is restored from `localStorage`
- AND the selected publications are not cleared merely because no user is signed in

---

### Requirement: Session Persistence

The system SHALL maintain an authenticated session across browser restarts.

#### Scenario: Session restored after browser close

- GIVEN an authenticated user closes and reopens their browser
- WHEN the application loads
- THEN the user is still authenticated without needing to sign in again

---

### Requirement: Guest-to-Authenticated Migration

The system SHALL migrate guest data to the user's account on first sign-in.

#### Scenario: localStorage data migrated on sign-in

- GIVEN a guest user has configured an issue in `localStorage`
- WHEN the user completes sign-in
- THEN the guest configuration is persisted to the database under their user account
- AND `localStorage` is cleared of the migrated data

---

### Requirement: Automatic Profile Creation

The system SHALL automatically create a user profile record when a new Supabase Auth user is created.

#### Scenario: Profile created on signup

- GIVEN a new user signs up via magic link or Google OAuth
- WHEN the Supabase Auth `on_auth_user_created` trigger fires
- THEN a record is inserted into `public.profiles` with the user's id, email, and display name

---

### Requirement: Row Level Security

The system SHALL enforce Row Level Security on every table in the `public` schema. Browser clients (anon key or an authenticated JWT) can only access their own data; the backend and scheduler use the service role, which bypasses RLS.

- `publications` and `articles` are readable by everyone and writable only by the service role.
- Identity lives in Supabase Auth (`auth.users`); there is no `public.users` table, and clients cannot read `auth.users`.
- `issues` are accessible to their owner (linked through `user_issues`, or matching `target_email`).
- `user_issues` rows are accessible only to the user they belong to, and a user can only link themselves to an issue they can already access.
- `issue_publications` follow access to the parent issue.
- Guest issues (`status = 'guest'`) are accessible only to the browser holding the issue's `guest_token`, sent in the `x-guest-token` header.

#### Scenario: User cannot read another user's issues

- GIVEN two authenticated users each with their own issues
- WHEN user A queries the `issues` table for an issue owned by user B
- THEN no row is returned and user A's session does not reveal user B's data

#### Scenario: User cannot attach themselves to another user's issue

- GIVEN an issue owned by user B
- WHEN user A inserts a `user_issues` row linking A to that issue
- THEN the insert is rejected by RLS

#### Scenario: Guest issue is private to its creator

- GIVEN a guest issue created with `guest_token = T`
- WHEN a request without `x-guest-token: T` queries or updates it
- THEN no row is visible or modified

---

### Requirement: Account Ownership Integrity

The system SHALL reference Supabase Auth users from `user_issues.user_id` with a foreign key to `auth.users(id)` that cascades on delete, so a user's links never outlive their account.

#### Scenario: Link to a nonexistent user is rejected

- GIVEN a `user_issues` insert whose `user_id` is not in `auth.users`
- WHEN the insert runs
- THEN it fails with a foreign key violation

#### Scenario: Deleting an account removes its links but not its issues

- GIVEN a user linked to an issue through `user_issues`
- WHEN the user is deleted from `auth.users`
- THEN their `user_issues` rows are deleted
- AND the issue row remains (it is then unowned)

#### Scenario: Migration archives dangling links before deleting them

- GIVEN `user_issues` rows whose user is no longer in `auth.users`
- WHEN the foreign key migration runs
- THEN those rows are first copied to `public.user_issues_dangling_archive` and then deleted, so they can be restored

---

### Requirement: Sign Out

The system SHALL allow authenticated users to sign out, invalidating their current session.

#### Scenario: Sign out clears session

- GIVEN an authenticated user clicks "Sign out"
- WHEN the sign-out action is processed
- THEN the Supabase session is invalidated
- AND the user is returned to the unauthenticated (guest) state
- AND the selected publications are cleared

#### Scenario: Guest selection survives without sign-in

- GIVEN a visitor who has never signed in has selected publications
- WHEN the app loads or reloads
- THEN the selection is kept, because `localStorage` is the guest's only copy
- AND it is cleared only on a transition from signed-in to signed-out
