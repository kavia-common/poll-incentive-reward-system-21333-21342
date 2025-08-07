# Reward System Database Schema

## Tables

- users (id, username, email, is_admin, ...)
- polls (id, title, description, created_at, status, results_data, weightage)
- poll_responses (id, user_id, poll_id, response_data, submitted_at, awarded)
- rewards (id, user_id, poll_response_id, tokens_earned, awarded_at)
- token_accounts (id, user_id, total_tokens, available_tokens, updated_at)
- redemption_logs (id, user_id, requested_at, tokens_redeemed, status, external_reference, log_data)

## Key Relationships

- User has many PollResponses, Rewards, TokenAccount, RedemptionLogs
- Poll has many PollResponses
- PollResponse is unique for (user_id, poll_id)
- Reward is unique for poll_response_id

## Migrations

- Use alembic for schema management and upgrades.
- See the migrations/ directory.
