"""Test Scribe config flow."""
from unittest.mock import patch
from homeassistant import config_entries
from custom_components.scribe.const import DOMAIN

async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.scribe.config_flow.ScribeConfigFlow._validate_connection",
        return_value=True,
    ), patch(
        "custom_components.scribe.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "db_url": "postgresql://user:pass@host/db",
                "record_states": True,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Scribe"
    assert result2["data"] == {
        "db_url": "postgresql://user:pass@host/db",
        "record_states": True,
    }
    assert len(mock_setup_entry.mock_calls) == 1
