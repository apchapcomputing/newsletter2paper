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

The system SHALL enforce that users can only access their own issues, profiles, and issue_publications.

#### Scenario: User cannot read another user's issues

- GIVEN two authenticated users each with their own issues
- WHEN user A queries `GET /issues/{id}` for an issue owned by user B
- THEN a 403 or 404 response is returned and user A's session does not reveal user B's data

---

### Requirement: Sign Out

The system SHALL allow authenticated users to sign out, invalidating their current session.

#### Scenario: Sign out clears session

- GIVEN an authenticated user clicks "Sign out"
- WHEN the sign-out action is processed
- THEN the Supabase session is invalidated
- AND the user is returned to the unauthenticated (guest) state
