import io

import segno


def generate_ticket_qr_png(ticket_code: str, scale: int = 6, border: int = 4) -> bytes:
    qr = segno.make_qr(ticket_code)
    buffer = io.BytesIO()
    qr.save(buffer, kind="png", scale=scale, border=border)
    return buffer.getvalue()
