"""Registry of console tasks. Add new tasks here as they are built."""
from .base import TaskInfo

TASKS: list[TaskInfo] = [
    TaskInfo("offboarding", "Offboard employee",
             "Lock a leaving employee out of Microsoft 365: block sign-in, reset password, "
             "remove MFA methods and revoke every active session."),
    TaskInfo("new_employee", "New employee", "Create user, license, groups, mailbox.", available=False),
    TaskInfo("reset_password", "Reset password + sign out", "", available=False),
    TaskInfo("mailbox_access", "Mailbox access & forwarding", "", available=False),
    TaskInfo("signin_check", "Why can't this user sign in?", "", available=False),
    TaskInfo("guest_invite", "Invite a guest", "", available=False),
]
