import pytest
from luml.schemas.organization import OrganizationCreateIn
from luml.schemas.stats import StatsEmailSendCreate
from luml.schemas.user import CreateUserIn
from pydantic import ValidationError


def test_stats_email_send_description_length() -> None:
    """Test that description length is limited."""
    long_description = "a" * 1001
    with pytest.raises(ValidationError) as excinfo:
        StatsEmailSendCreate(email="test@example.com", description=long_description)

    # We expect a validation error about max_length
    # Pydantic default error message contains "String should have at most"
    assert "String should have at most" in str(excinfo.value)


def test_user_full_name_length() -> None:
    """Test that user full name length is limited."""
    long_name = "a" * 101
    with pytest.raises(ValidationError) as excinfo:
        CreateUserIn(
            email="test@example.com", password="password123", full_name=long_name
        )

    assert "String should have at most" in str(excinfo.value)


def test_organization_name_length() -> None:
    """Test that organization name length is limited."""
    long_name = "a" * 101
    with pytest.raises(ValidationError) as excinfo:
        OrganizationCreateIn(name=long_name)

    assert "String should have at most" in str(excinfo.value)
