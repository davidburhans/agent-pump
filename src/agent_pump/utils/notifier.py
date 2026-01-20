"""Notification utility using plyer."""

import logging

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
