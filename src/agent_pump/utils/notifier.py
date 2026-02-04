"""Notification utility using plyer."""

import logging
import os

logger = logging.getLogger(__name__)


class Notifier:
    """Handles sending desktop notifications."""

    @staticmethod
    def send(title: str, message: str, app_name: str = "Agent Pump", timeout: int = 10) -> None:
        """
        Send a desktop notification.

        Args:
            title: Notification title
            message: Notification body
            app_name: Name of the application sending the notification
            timeout: Duration in seconds to show the notification
        """
        # Check for environment variable to disable notifications (e.g., during tests)
        if os.environ.get("AGENT_PUMP_NO_NOTIFY", "").lower() in ("true", "1", "yes"):
            logger.debug("Notifications disabled via AGENT_PUMP_NO_NOTIFY")
            return

        try:
            from plyer import notification

            if notification and hasattr(notification, "notify"):
                notification.notify(  # type: ignore
                    title=title, message=message, app_name=app_name, timeout=timeout
                )
                logger.debug(f"Notification sent: {title} - {message}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    @staticmethod
    def test() -> None:
        """Send a test notification."""
        Notifier.send("Agent Pump", "This is a test notification from Agent Pump.")

    @staticmethod
    def send_approval_request(
        project_name: str,
        phase: str,
        feature: str | None = None,
        timeout_minutes: int = 0,
    ) -> None:
        """Send a notification for an approval request.

        Args:
            project_name: Name of the project requiring approval
            phase: Workflow phase requiring approval
            feature: Current feature being worked on (if any)
            timeout_minutes: Minutes until auto timeout (0 = no timeout)
        """
        title = f"⏸ Approval Required: {project_name}"

        if feature:
            message = f"Phase '{phase}' for feature '{feature}' needs your approval."
        else:
            message = f"Phase '{phase}' needs your approval."

        if timeout_minutes > 0:
            message += f"\nAuto-approval in {timeout_minutes} minutes."

        Notifier.send(title, message, timeout=15)

    @staticmethod
    def send_approval_timeout_warning(
        project_name: str,
        phase: str,
        minutes_remaining: int,
    ) -> None:
        """Send a warning notification before approval timeout.

        Args:
            project_name: Name of the project
            phase: Workflow phase
            minutes_remaining: Minutes until timeout
        """
        title = f"⚠ Approval Timeout Warning: {project_name}"
        message = f"Approval for phase '{phase}' expires in {minutes_remaining} minutes."

        Notifier.send(title, message, timeout=10)
