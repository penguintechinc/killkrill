# Database Seeding - User Initialization

## Overview

The Flask backend automatically seeds default users on startup to ensure the system is always accessible.

## Seeding Behavior

### Admin User (ALL Environments)

The admin user is **ALWAYS** created if it doesn't exist, regardless of environment (development, testing, production):

| Field    | Value              |
|----------|--------------------|
| Email    | admin@penguintech.io    |
| Password | admin123           |
| Role     | admin              |
| Name     | Administrator      |

**Why Always Seed Admin?**
- Ensures there's always a way to log into the system
- Prevents lockout scenarios in production
- Required for initial system configuration
- Safe because it checks for existence first (idempotent)

### Mock Users (Development/Alpha Only)

Additional test users are created **ONLY** in development and testing environments:

| Email                  | Password  | Role       |
|------------------------|-----------|------------|
| maintainer@penguintech.io   | admin123  | maintainer |
| viewer@penguintech.io       | admin123  | viewer     |

**Why Only in Alpha?**
- Mock data should not exist in production
- Reduces security surface area in beta/prod
- Follows principle of least privilege

## Implementation

### Location

Seeding functions are implemented in:
```
services/flask-backend/app/models/db_init.py
```

Two separate functions handle seeding:
- `seed_admin_user()` - Called in ALL environments
- `seed_mock_users()` - Called ONLY in development/testing

### Invocation

Seeding occurs automatically during app initialization in `create_app()`:

```python
# ALWAYS seed admin user (all environments) if it doesn't exist
seed_admin_user()

# Seed mock users ONLY in development/alpha environment
if app_config.env in ("development", "testing"):
    seed_mock_users()
```

## Security Considerations

### Default Password

The default password `admin123` is:
- ✅ Simple and memorable for initial setup
- ⚠️ Should be changed immediately after first login
- 🔒 Users can change password via `/api/v1/auth/change-password`

### Password Change Endpoint

Users should change from the default password using:

```bash
curl -X POST http://localhost:5000/api/v1/auth/change-password \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "current_password":"admin123",
    "new_password":"MySecurePassword123"
  }'
```

### Password Requirements

New passwords must meet these criteria:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit

## Idempotency

All seeding functions are **idempotent** - they can be called multiple times safely:

1. Check if user exists by email
2. If exists, skip creation and log
3. If not exists, create user
4. Safe to restart app without duplicating users

## Environment Detection

Environment is determined by `FLASK_ENV` variable:
- `development` - Alpha environment, all users seeded
- `testing` - Test environment, all users seeded
- `production` - Production environment, admin only seeded

## Manual Seeding

While seeding happens automatically on startup, you can manually trigger it:

```python
from app.models.db_init import seed_admin_user, seed_mock_users

# Seed admin (safe in all environments)
seed_admin_user()

# Seed mock users (only do this in development)
seed_mock_users()
```

## Logs

Seeding operations are logged for audit purposes:

```json
{
  "event": "Created default admin user",
  "email": "admin@penguintech.io",
  "role": "admin"
}
```

Or if user already exists:

```json
{
  "event": "Admin user already exists",
  "email": "admin@penguintech.io"
}
```

## Troubleshooting

### Admin User Not Created

If admin user is not created automatically:

1. Check logs for `seed_admin_user_error` warnings
2. Verify database connection is working
3. Ensure PyDAL tables are initialized
4. Check that `hash_password` function is importable

### Password Not Working

If default password doesn't work:

1. Verify you're using email format: `admin@penguintech.io`
2. Check password is exactly `admin123` (case-sensitive)
3. Ensure no spaces in password
4. Try password reset if user was previously created with different password

## Best Practices

1. **Change Default Password**: Always change `admin123` after first login
2. **Remove Mock Users in Production**: Verify mock users don't exist in production
3. **Use Strong Passwords**: Follow password requirements for new passwords
4. **Monitor Login Attempts**: Watch for failed login attempts on default accounts
5. **Regular Password Rotation**: Encourage users to change passwords periodically

## Future Enhancements

Potential improvements to seeding:
- [ ] Environment variable for custom admin email
- [ ] Environment variable for custom admin password
- [ ] Force password change on first login flag
- [ ] Admin account lockout after N failed attempts
- [ ] Email notification when default account is used
