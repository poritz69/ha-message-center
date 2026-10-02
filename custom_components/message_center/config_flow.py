"""Config flow: pick the phones that receive pushes.

Everything else is set on the integration's page. Only one message center
can exist (single_config_entry in the manifest).
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from .const import CONF_RECIPIENTS, DOMAIN
from .delivery import Recipient, discover_mobile_apps


class MessageCenterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup and reconfiguration."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick recipients and create the entry."""
        return await self._async_step_recipients("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the recipients of the existing entry."""
        return await self._async_step_recipients("reconfigure", user_input)

    async def _async_step_recipients(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        found = {r.action: r for r in discover_mobile_apps(self.hass)}
        if not found:
            return self.async_abort(reason="no_mobile_app")

        errors: dict[str, str] = {}
        if user_input is not None and not user_input[CONF_RECIPIENTS]:
            # without a recipient every message would fail right away
            errors[CONF_RECIPIENTS] = "at_least_one"
        elif user_input is not None:
            recipients = [
                found[action].to_dict() for action in user_input[CONF_RECIPIENTS]
            ]
            if step_id == "reconfigure":
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates={CONF_RECIPIENTS: recipients},
                )
            return self.async_create_entry(
                title="Message Center", data={CONF_RECIPIENTS: recipients}
            )

        current: list[str] = []
        if step_id == "reconfigure":
            current = [
                Recipient.from_dict(item).action
                for item in self._get_reconfigure_entry().data.get(CONF_RECIPIENTS, [])
                if item.get("action") in found
            ]
        schema = vol.Schema(
            {
                vol.Required(CONF_RECIPIENTS, default=current): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=r.action, label=r.name)
                            for r in found.values()
                        ],
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)
