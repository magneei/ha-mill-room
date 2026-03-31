"""Config flow for Mill Room integration."""

from __future__ import annotations

import logging
from typing import Any

import mill
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class MillRoomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mill Room."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            mill_client = mill.Mill(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                if not await mill_client.connect():
                    errors["base"] = "auth_failed"
            except Exception:
                _LOGGER.exception("Unexpected error during Mill connection")
                errors["base"] = "cannot_connect"
            finally:
                await mill_client.close_connection()

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
