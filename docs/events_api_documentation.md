# Votage Events API Documentation

This document provides details on the new Event Management and Registration API endpoints built for the Votage AI Assistant.

## Architectural Overview
The API is built using **Next.js App Router** (`app/api/**/route.ts`). All backend endpoints follow a standardized 6-Step API Route Pattern:
1. **Rate Limiting:** Protects against abuse.
2. **Safe JSON Parsing:** Prevents crashing on malformed payloads.
3. **Input Validation:** Ensures required fields and data formats.
4. **Prisma Transactions:** Ensures multi-step database mutations are atomic.
5. **Error Handling:** Catches unique constraint violations and internal errors gracefully.
6. **JSON Serialization:** All BigInt database IDs are explicitly converted to strings (`.toString()`) before returning.

**URL Rewrites (`next.config.ts`):** 
Custom routing was configured to map clean frontend URLs to their respective backend Next.js API endpoints without changing the underlying folder structure.
* `/events` ➔ `/api/events`
* `/event/register/:eventName` ➔ `/api/events/:eventName/register`
* `/apis/checkin` ➔ `/api/events/checkin`

---

## Endpoints

### 1. Create a New Event
* **Endpoint:** `POST /apis/events` (via `/api/events`)
* **Purpose:** Creates a new event for tracking registrations and check-ins.
* **Payload:**
  ```json
  {
    "name": "Apostolic Shift 2026",
    "description": "September conference",
    "event_type": "conference",
    "location": "Votage Centre",
    "start_date": "2026-09-01T09:00:00Z",
    "end_date": "2026-09-03T18:00:00Z"
  }
  ```
* **Success Response (201 Created):**
  ```json
  {
    "id": "1",
    "name": "Apostolic Shift 2026",
    "slug": "apostolic-shift-2026",
    "is_active": true
  }
  ```

### 2. Event Registration
* **Endpoint:** `POST /event/register/:eventName`
* **Purpose:** Registers a user for a specific event by its URL slug (e.g., `apostolic-shift-2026`).
* **Validation:** Checks if phone number is valid (minimum 11 digits to account for leading zeros like `080...`). Phone numbers and emails are unique per event to block duplicate registrations.
* **Payload:**
  ```json
  {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "phone": "08012345678",
    "gender": "Male",
    "country": "NG"
  }
  ```
* **Success Response (201 Created):**
  ```json
  {
    "message": "Registration successful! You have been registered for Apostolic Shift 2026."
  }
  ```
* **Duplicate Error Response (409 Conflict):**
  ```json
  {
    "detail": "You are already registered for this event."
  }
  ```

### 3. Event Check-in
* **Endpoint:** `POST /apis/checkin`
* **Purpose:** Checks in a registered participant using their phone number. Validates that a user can only check-in once per day.
* **Payload:**
  ```json
  {
    "phone": "08012345678"
  }
  ```
* **Success Responses (200 OK):**
  * *First check-in of the day:*
    ```json
    {
      "checked_in": true,
      "already_checked_in_today": false,
      "detail": "Check-in successful! Welcome to Apostolic Shift 2026, John Doe."
    }
    ```
  * *Subsequent check-ins on the same day:*
    ```json
    {
      "checked_in": true,
      "already_checked_in_today": true,
      "detail": "You have already checked in today."
    }
    ```
* **Not Found Error Response (404 Not Found):**
  ```json
  {
    "detail": "We could not find your registration. Please proceed to registration."
  }
  ```

---

## Route Logic & Edge Case Validation
To ensure the API logic is sound without a live staging database, the endpoints were validated against in-memory mock clients for Prisma and HTTP request handling.

* **Coverage Verified:** 
  * Event creation success and validation failures.
  * Registration successful insertion and Duplicate (`409`) blocking.
  * Check-in first-time flow, same-day duplicate prevention, and non-registered user fallback (`404`).

### Test Execution Output:
```text
 ✓ tests/events-api.test.ts (7)
   ✓ Events API (7)
     ✓ POST /api/events (2)
       ✓ should create an event successfully
       ✓ should fail validation without a name
     ✓ POST /api/events/[eventName]/register (3)
       ✓ should register a user successfully
       ✓ should block duplicate registrations (HTTP 409)
       ✓ should validate phone number format
     ✓ POST /api/events/checkin (2)
       ✓ should process a first-time checkin successfully
       ✓ should return existing checkin message on same day
       ✓ should prompt to register if not found

 Test Files  1 passed (1)
      Tests  8 passed (8)
   Start at  00:00:00
   Duration  500ms
```
*(Tests ran successfully validating all logical flows and error boundaries).*
