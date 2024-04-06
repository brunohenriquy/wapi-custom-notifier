import logging
import voluptuous as vol
import requests
import homeassistant.helpers.config_validation as cv
import time
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    PLATFORM_SCHEMA,
    BaseNotificationService
)

CONF_URL = 'url'
CONFIG_SESSION = 'session'
CONFIG_TOKEN = 'token'
_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONFIG_SESSION): cv.string,
    vol.Optional(CONFIG_TOKEN): cv.string,
}, extra=vol.ALLOW_EXTRA)


def get_service(hass, config, discovery_info=None):
    """Get the custom notifier service."""
    url = config.get(CONF_URL)
    session = config.get(CONFIG_SESSION)
    token = config.get(CONFIG_TOKEN)
    return MatterNotificationService(url, session, token)


class MatterNotificationService(BaseNotificationService):
    def __init__(self, url, session, token=None):
        self._url = url
        self.session = session
        self.token = token

    def delete_message_for_myself(self, chat_id, message_id, headers):
        if message_id:
            data_delete = {

                "chatId": chat_id,
                "messageId": message_id,
                "everyone": False

            }

            max_retries = 10
            retry_count = 0
            wait_seconds = 5
            while retry_count < max_retries:
                try:
                    response = requests.post(self._url + "/message/delete/" + self.session, json=data_delete,
                                             headers=headers)
                    if response.json().get("success", False):
                        _LOGGER.info("WAPI - Message deleted for myself")
                        break
                    else:
                        _LOGGER.info(
                            f"WAPI - Message not deleted - not found yet, trying again in {wait_seconds} seconds"
                        )
                        time.sleep(wait_seconds)
                        retry_count += 1
                except Exception as ex:
                    _LOGGER.info(f"WAPI - Message not deleted - error, trying again in {wait_seconds} seconds: {ex}")
                    time.sleep(wait_seconds)
                    retry_count += 1

            response.raise_for_status()
        else:
            _LOGGER.error("WAPI - Message not deleted for myself, message id not found")

    def send_message(self, message="", **kwargs):
        title = kwargs.get(ATTR_TITLE)
        chat_id = kwargs.get(ATTR_TARGET)
        data = kwargs.get(ATTR_DATA)

        delete_for_myself_after_send = False
        if data:
            delete_for_myself_after_send = data.get("delete_for_myself_after_send", False)

        data_send = {

            "content": "*" + title + "* \n" + message,
            "chatId": chat_id,
            "contentType": "string"

        }

        try:
            headers = {}
            if self.token:
                headers = {"x-api-key": self.token}

            response = requests.post(self._url + "/client/sendMessage/" + self.session, json=data_send, headers=headers)
            response.raise_for_status()

            message_id = response.json().get("message", {}).get("_data", {}).get("id", {}).get("id", None)
            _LOGGER.info(f"WAPI - Message sent, ID: {message_id}")

            if delete_for_myself_after_send:
                self.delete_message_for_myself(chat_id, message_id, headers)

        except requests.exceptions.RequestException as ex:
            _LOGGER.error(f"WAPI - Error sending notification: {ex}")
