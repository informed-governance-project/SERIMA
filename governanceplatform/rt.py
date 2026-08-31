"""Request Tracker REST transport.

Nothing here knows about incidents: every function takes an Observer, which is a
governanceplatform model. Recording which RT ticket belongs to which incident is the
incidents app's job — see incidents.email.create_or_update_rt_ticket.
"""

import logging
from urllib.parse import quote, urlparse

import requests
from django.core.exceptions import ValidationError

from .settings import EMAIL_SENDER
from .validators import validate_rt_url

logger = logging.getLogger(__name__)


def rt_request(method: str, url: str, **kwargs):
    """
    Issue a request to the RT API, revalidating the target first.

    Redirects are refused: a host that passes validation must not be able to bounce the
    request on to an address the validator never saw.
    """
    validate_rt_url(url)
    return requests.request(method, url, allow_redirects=False, timeout=(5, 30), **kwargs)


def _headers(observer) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"token {observer.rt_token}",
    }


def create_rt_ticket(observer, subject: str, content: str) -> str | None:
    """Open a new RT ticket, returning its id, or None if RT would not create one."""
    base_url = observer.rt_url.rstrip("/")
    payload = {
        "Requestor": EMAIL_SENDER,
        "Queue": observer.rt_queue,
        "Subject": subject,
        "Content": content,
        "ContentType": "text/html",
    }

    try:
        response = rt_request("POST", f"{base_url}/REST/2.0/ticket", json=payload, headers=_headers(observer))
    except ValidationError:
        logger.error("Blocked unsafe RT URL: %s", base_url)
        return None
    except requests.RequestException as e:
        logger.error("Error connecting to RT API: %s", e)
        return None

    if not response.ok:
        logger.error("RT API Error %s: %s", response.status_code, response.text)
        return None

    if response.status_code != 201:
        return None

    return response.json().get("id")


def add_rt_correspondence(observer, ticket_id: str, content: str) -> bool:
    """Append a reply to an RT ticket that already exists."""
    base_url = observer.rt_url.rstrip("/")

    try:
        response = rt_request(
            "POST",
            f"{base_url}/REST/2.0/ticket/{ticket_id}/correspond",
            json={"Content": content, "ContentType": "text/html"},
            headers=_headers(observer),
        )
    except ValidationError:
        logger.error("Blocked unsafe RT URL: %s", base_url)
        return False
    except requests.RequestException as e:
        logger.error("Error connecting to RT API: %s", e)
        return False

    if not response.ok:
        logger.error("RT API Error %s: %s", response.status_code, response.text)
        return False

    return True


def check_rt_config(observer) -> bool:
    if not observer.rt_url or not observer.rt_queue or not observer.rt_token:
        return False

    parsed = urlparse(observer.rt_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    encoded_queue = quote(observer.rt_queue, safe="")
    url = f"{base_url}/REST/2.0/queue/{encoded_queue}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"token {observer.rt_token}",
    }
    try:
        response = rt_request("GET", url, headers=headers)
        if response.status_code == 200:
            return True
        if response.status_code == 401:
            logger.warning("RT token unauthorized (401) for %s", str(observer))
        elif response.status_code == 404:
            logger.warning("RT queue '%s' not found at %s", observer.rt_queue, url)
        else:
            logger.warning("Unexpected RT response (%s): %s", response.status_code, response.text)
        return False
    except ValidationError:
        logger.error("Blocked unsafe RT URL: %s", base_url)
        return False
    except requests.RequestException as e:
        logger.error("Error connecting to RT API: %s", e)
        return False
