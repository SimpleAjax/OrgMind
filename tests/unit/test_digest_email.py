import pytest
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

from orgmind.integrations.email.service import EmailService
from orgmind.engine.digest_engine import DigestEngine
from orgmind.storage.models_traces import DecisionTraceModel

# --- Email Service Tests ---

def test_email_service_send(mocker):
    # Mock smtplib
    mock_smtp_cls = mocker.patch("smtplib.SMTP")
    mock_server = mock_smtp_cls.return_value.__enter__.return_value
    
    service = EmailService()
    # Override settings for test
    service.host = "localhost"
    service.port = 1025
    
    result = service.send_html_email(["test@example.com"], "Subject", "<h1>Hello</h1>")
    
    assert result is True
    mock_smtp_cls.assert_called_with("localhost", 1025)
    mock_server.sendmail.assert_called_once()
    args, _ = mock_server.sendmail.call_args
    assert args[1] == ["test@example.com"]
    assert "Subject: Subject" in args[2]

def test_email_service_fail(mocker):
    mock_smtp_cls = mocker.patch("smtplib.SMTP")
    mock_smtp_cls.side_effect = Exception("Connection Refused")
    
    service = EmailService()
    result = service.send_html_email(["test@example.com"], "Subject", "<h1>Hello</h1>")
    
    assert result is False

# --- Digest Engine Tests ---

@pytest.fixture
def mock_email_service():
    return MagicMock(spec=EmailService)

@pytest.fixture
def mock_session():
    return MagicMock()

def test_digest_generation(mock_email_service, mock_session):
    engine = DigestEngine(mock_email_service)
    
    # Mock Data
    user_email = "user@example.com"
    now = datetime.utcnow()
    
    # Mock methods instead of DB queries
    with patch.object(engine, '_get_total_traces_count', return_value=10) as mock_total, \
         patch.object(engine, '_get_missing_context_traces') as mock_missing:
         
        t1 = DecisionTraceModel(action_type="View", timestamp=now)
        t2 = DecisionTraceModel(action_type="Edit", timestamp=now)
        mock_missing.return_value = [t1, t2]

        engine.generate_and_send_digest(mock_session, user_email)
        
        # Verify calls
        mock_total.assert_called_once()
        mock_missing.assert_called_once()

    # Verify Email Sent
    mock_email_service.send_html_email.assert_called_once()
    args, _ = mock_email_service.send_html_email.call_args
    
    assert args[0] == [user_email]
    assert "Weekly OrgMind Decision Digest" in args[1]
    msg_body = args[2]
    
    # formatting check
    assert "<b>10</b>" in msg_body # Total
    assert "Decisions Missing Context: <b style=\"color: red;\">2</b>" in msg_body
    assert "View" in msg_body
    assert "Edit" in msg_body

def test_digest_generation_skipped(mock_email_service, mock_session):
    engine = DigestEngine(mock_email_service)
    
    with patch.object(engine, '_get_total_traces_count', return_value=0):
        engine.generate_and_send_digest(mock_session, "user@example.com")
        
    mock_email_service.send_html_email.assert_not_called()
