import os
import sys
from unittest.mock import MagicMock, patch
from agent_pump.utils.notifier import Notifier

def test_notifier_sends_notification_by_default():
    """Test that notification is sent when env var is NOT set."""
    # Mock plyer
    mock_plyer = MagicMock()
    mock_notification = MagicMock()
    mock_plyer.notification = mock_notification
    
    # Ensure env var is not set
    # Note: we use clear=False and explicitly pop the key if it exists to preserve other env vars
    # but patch.dict with empty dict and clear=True clears EVERYTHING which might break other things?
    # Better to just patch the specific key we care about not being there.
    # But since we want to ensure it is NOT there, we can use patch.dict(os.environ) and del if needed.
    # actually patch.dict(os.environ, {"KEY": "VAL"}) sets it. To unset, we might need verify it's not there.
    
    with patch.dict(os.environ):
        if "AGENT_PUMP_NO_NOTIFY" in os.environ:
            del os.environ["AGENT_PUMP_NO_NOTIFY"]
            
        # We need to mock sys.modules so 'import plyer' inside the function works and returns our mock
        with patch.dict("sys.modules", {"plyer": mock_plyer}):
            Notifier.send("Title", "Message")
            
            mock_notification.notify.assert_called_once_with(
                title="Title", 
                message="Message", 
                app_name="Agent Pump", 
                timeout=10
            )

def test_notifier_respects_disable_env_var():
    """Test that notification is NOT sent when AGENT_PUMP_NO_NOTIFY is set."""
    # Mock plyer
    mock_plyer = MagicMock()
    mock_notification = MagicMock()
    mock_plyer.notification = mock_notification
    
    # Set env var
    with patch.dict(os.environ, {"AGENT_PUMP_NO_NOTIFY": "true"}):
        with patch.dict("sys.modules", {"plyer": mock_plyer}):
            Notifier.send("Title", "Message")
            
            mock_notification.notify.assert_not_called()

def test_notifier_respects_disable_env_var_case_insensitive():
    """Test that notification is NOT sent when AGENT_PUMP_NO_NOTIFY is set (case insensitive)."""
    # Mock plyer
    mock_plyer = MagicMock()
    mock_notification = MagicMock()
    mock_plyer.notification = mock_notification
    
    # Set env var
    with patch.dict(os.environ, {"AGENT_PUMP_NO_NOTIFY": "TRUE"}):
        with patch.dict("sys.modules", {"plyer": mock_plyer}):
            Notifier.send("Title", "Message")
            
            mock_notification.notify.assert_not_called()
