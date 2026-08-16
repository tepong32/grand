from __future__ import annotations

from io import BytesIO
from urllib.parse import quote, urljoin, urlsplit

import qrcode


class QRPayloadError(ValueError):
    pass


def _base_url(base_url):
    if not base_url:
        return "/"
    parsed = urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise QRPayloadError("QR links require an HTTP or HTTPS portal address.")
    return base_url.rstrip("/") + "/"


def packet_qr_payload(packet, *, base_url=""):
    path = f"tracepoint/scan/packet/{packet.public_id}/"
    return urljoin(_base_url(base_url), path)


def employee_qr_payload(token, *, base_url=""):
    if not token or "/" in token:
        raise QRPayloadError("The daily employee token is malformed.")
    path = f"tracepoint/scan/employee/{quote(token, safe='-_')}/"
    return urljoin(_base_url(base_url), path)


def render_qr_png(payload):
    code = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    code.add_data(payload)
    code.make(fit=True)
    image = code.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
