import importlib
from typing import Dict, List, Union

from fastapi import HTTPException, Request, status
from starlette.datastructures import FormData

from services.settings import get_settings


def _form_data_to_dict(form_data: FormData) -> Dict[str, Union[str, List[str]]]:
    payload: Dict[str, Union[str, List[str]]] = {}
    for key, value in form_data.multi_items():
        existing = payload.get(key)
        if existing is None:
            payload[key] = value
            continue
        if isinstance(existing, list):
            existing.append(value)
            continue
        payload[key] = [existing, value]
    return payload


def _public_request_url(request: Request) -> str:
    url = request.url
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")

    if forwarded_proto or forwarded_host:
        url = url.replace(
            scheme=forwarded_proto or url.scheme,
            netloc=forwarded_host or url.netloc,
        )

    return str(url)


def validate_twilio_request(request: Request, form_data: FormData) -> None:
    settings = get_settings()
    if not settings.validate_twilio_signature:
        return

    try:
        validator_class = getattr(
            importlib.import_module("twilio.request_validator"),
            "RequestValidator",
        )
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio SDK is not installed",
        ) from exc

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing Twilio signature",
        )

    validator = validator_class(settings.twilio_auth_token)
    expected_url = _public_request_url(request)
    params = _form_data_to_dict(form_data)

    if not validator.validate(expected_url, params, signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Twilio request validation failed",
        )
