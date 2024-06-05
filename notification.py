import requests # type: ignore
from requests.exceptions import ConnectionError, HTTPError # type: ignore

from exponent_server_sdk import (   # type: ignore
    DeviceNotRegisteredError,
    PushClient,
    PushMessage,
    PushServerError,
    PushTicketError,
)

session = requests.Session()
session.headers.update(
    {
        "accept": "application/json",
        "accept-encoding": "gzip, deflate",
        "content-type": "application/json",
    }
)

def send_push_message(token, title, message, extra=None):
    try:
        response = PushClient(session=session).publish(
            PushMessage(to=token,
                        title=title,
                        body=message,
                        data=extra))
    except PushServerError as exc:
        # Encountered some likely formatting/validation error.
        raise
    except (ConnectionError, HTTPError) as exc:
        pass

    try:
        # We got a response back, but we don't know whether it's an error yet.
        # This call raises errors so we can handle them with normal exception
        # flows.
        response.validate_response()
    except DeviceNotRegisteredError:
        # Mark the push token as inactive
        pass
    except PushTicketError as exc:
        # Encountered some other per-notification error.
        raise
