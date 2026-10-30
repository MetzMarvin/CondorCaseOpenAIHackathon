"""Deterministic PDF documents and raster document images; standard library only.

These are visibly synthetic reports, tags and receipts, not real airline forms.
PNG text uses a tiny built-in bitmap alphabet so builds need no fonts or packages.
"""

import binascii
import struct
import zlib


def plan(tag, category, scenario, facts):
    """Return initial and held-back upload specifications; no fixture truth in runtime metadata."""
    common = {"booking_reference": facts["booking_reference"], "flight_number": facts["flight_number"],
              "flight_date": facts["flight_date"], "route": f'{facts["origin"]} / {facts["destination"]}'}
    def spec(kind, media, suffix, *, wrong=False, readable=True):
        fields = dict(common)
        if wrong:
            fields["booking_reference"] = "MOCK-UNRELATED"
        if category == "baggage":
            fields.update(baggage_status="NOT DELIVERED", bag_description="BLACK HARD SHELL SUITCASE")
            if kind == "baggage_report":
                fields["pir_reference"] = facts["pir_reference"]
                if scenario != "missing_bag_tag" or suffix.startswith("FOLLOWUP"):
                    fields["bag_tag"] = facts["bag_tag"]
            if kind == "baggage_tag":
                fields["bag_tag"] = facts["bag_tag"]
        if kind == "receipt":
            fields["amount_eur"] = facts["expense_eur"]
        extension = "pdf" if media == "application/pdf" else "png"
        return {"id": f"ATTACH-{tag}-{suffix}", "kind": kind, "media_type": media,
                "path": f"attachments/ATTACH-{tag}-{suffix}.{extension}", "fields": fields, "readable": readable}
    if category == "baggage":
        if scenario == "unreadable_document":
            initial = [spec("baggage_report", "image/png", "OBSCURED", readable=False),
                       spec("receipt", "application/pdf", "RECEIPT")]
        else:
            initial = []
            if scenario != "missing_pir":
                initial.append(spec("baggage_report", "application/pdf", "PIR"))
            if scenario != "missing_bag_tag":
                initial.append(spec("baggage_tag", "image/png", "TAG"))
            if scenario != "missing_receipt":
                initial.append(spec("receipt", "image/png", "RECEIPT", wrong=scenario == "conflicting_evidence"))
    else:
        kind = "receipt" if category in ("baggage", "service") or scenario in ("missing_receipt", "conflicting_evidence") else "booking_confirmation"
        initial = [] if scenario == "missing_receipt" else [spec(kind, "application/pdf", "DOCUMENT", wrong=scenario == "conflicting_evidence")]
    replacements = {"missing_receipt": ("receipt", "application/pdf"), "missing_pir": ("baggage_report", "application/pdf"),
                    "missing_bag_tag": ("baggage_tag", "image/png"), "unreadable_document": ("baggage_report", "application/pdf"),
                    "conflicting_evidence": ("receipt", "application/pdf")}
    followup = [spec(*replacements[scenario], "FOLLOWUP")] if scenario in replacements else []
    return initial, followup


FONT = dict(zip(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.:/ ()?",
    ["01110/10001/10001/11111/10001/10001/10001", "11110/10001/10001/11110/10001/10001/11110",
     "01111/10000/10000/10000/10000/10000/01111", "11110/10001/10001/10001/10001/10001/11110",
     "11111/10000/10000/11110/10000/10000/11111", "11111/10000/10000/11110/10000/10000/10000",
     "01111/10000/10000/10111/10001/10001/01111", "10001/10001/10001/11111/10001/10001/10001",
     "11111/00100/00100/00100/00100/00100/11111", "00111/00010/00010/00010/10010/10010/01100",
     "10001/10010/10100/11000/10100/10010/10001", "10000/10000/10000/10000/10000/10000/11111",
     "10001/11011/10101/10101/10001/10001/10001", "10001/11001/10101/10011/10001/10001/10001",
     "01110/10001/10001/10001/10001/10001/01110", "11110/10001/10001/11110/10000/10000/10000",
     "01110/10001/10001/10001/10101/10010/01101", "11110/10001/10001/11110/10100/10010/10001",
     "01111/10000/10000/01110/00001/00001/11110", "11111/00100/00100/00100/00100/00100/00100",
     "10001/10001/10001/10001/10001/10001/01110", "10001/10001/10001/10001/10001/01010/00100",
     "10001/10001/10001/10101/10101/10101/01010", "10001/10001/01010/00100/01010/10001/10001",
     "10001/10001/01010/00100/00100/00100/00100", "11111/00001/00010/00100/01000/10000/11111",
     "01110/10001/10011/10101/11001/10001/01110", "00100/01100/00100/00100/00100/00100/01110",
     "01110/10001/00001/00010/00100/01000/11111", "11110/00001/00001/01110/00001/00001/11110",
     "00010/00110/01010/10010/11111/00010/00010", "11111/10000/10000/11110/00001/00001/11110",
     "01110/10000/10000/11110/10001/10001/01110", "11111/00001/00010/00100/01000/01000/01000",
     "01110/10001/10001/01110/10001/10001/01110", "01110/10001/10001/01111/00001/00001/01110",
     "00000/00000/00000/11111/00000/00000/00000", "00000/00000/00000/00000/00000/00100/00100",
     "00000/00100/00100/00000/00100/00100/00000", "00001/00010/00010/00100/01000/01000/10000",
     "00000/00000/00000/00000/00000/00000/00000", "00010/00100/01000/01000/01000/00100/00010",
     "01000/00100/00010/00010/00010/00100/01000", "01110/10001/00001/00010/00100/00000/00100"]
))


def document_lines(spec):
    fields = spec["fields"]
    titles = {"baggage_report": "BAGGAGE IRREGULARITY REPORT", "baggage_tag": "BAGGAGE TAG",
              "receipt": "ESSENTIAL PURCHASES RECEIPT", "booking_confirmation": "BOOKING CONFIRMATION"}
    lines = ["DEMO - SYNTHETIC TEST DOCUMENT", titles[spec["kind"]], ""]
    labels = {"booking_reference": "BOOKING", "flight_number": "FLIGHT", "flight_date": "DATE",
              "route": "ROUTE", "pir_reference": "PIR REFERENCE", "bag_tag": "BAG TAG",
              "bag_description": "BAG DESCRIPTION", "baggage_status": "BAG STATUS", "amount_eur": "TOTAL EUR"}
    for key, label in labels.items():
        if fields.get(key) is not None:
            lines.append(f"{label}: {fields[key]}")
    if spec["kind"] == "receipt":
        lines.extend(["ITEM: ESSENTIAL TOILETRIES", "PAYMENT: PAID - DEMO"])
    lines.extend(["", "NOT VALID FOR TRAVEL OR PAYMENT"])
    return lines


def pdf_bytes(lines):
    def literal(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    commands = ["BT /F1 12 Tf 50 780 Td 21 TL"]
    for i, line in enumerate(lines):
        if i:
            commands.append("T*")
        commands.append(f"({literal(line)}) Tj")
    commands.append("ET")
    content = "\n".join(commands).encode("ascii")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def png_bytes(lines, readable=True):
    scale, margin, line_height = 3, 28, 32
    width = max(720, max(map(len, lines))*6*scale + 2*margin)
    height = len(lines)*line_height + 2*margin
    pixels = bytearray(b"\xff" * width * height)
    for row_index, line in enumerate(lines):
        for char_index, char in enumerate(line.upper()):
            glyph = FONT.get(char, FONT["?"]).split("/")
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        x = margin + char_index*6*scale + gx*scale
                        y = margin + row_index*line_height + gy*scale
                        for dy in range(scale):
                            start = (y+dy)*width+x
                            pixels[start:start+scale] = b"\x18"*scale
    if not readable:
        # Valid decodable image, with all substantive fields physically obscured.
        for y in range(margin+3*line_height, height-margin):
            start = y*width+margin
            pixels[start:start+width-2*margin] = b"\x55"*(width-2*margin)
    raw = b"".join(b"\0"+pixels[y*width:(y+1)*width] for y in range(height))
    def chunk(kind, content):
        return struct.pack(">I",len(content))+kind+content+struct.pack(">I",binascii.crc32(kind+content)&0xffffffff)
    return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,0,0,0,0))+chunk(b"IDAT",zlib.compress(raw,9))+chunk(b"IEND",b"")


def render(spec):
    lines = document_lines(spec)
    return pdf_bytes(lines) if spec["media_type"] == "application/pdf" else png_bytes(lines, spec["readable"])


def inspect_binary(content, media_type):
    """Decode PNG structure/CRC/pixels or check PDF structure; OCR is deliberately separate."""
    if media_type == "application/pdf":
        return content.startswith(b"%PDF-1.4") and content.endswith(b"%%EOF\n") and b"/Type /Page " in content
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset, image_data, width, height = 8, b"", 0, 0
    try:
        while offset < len(content):
            size = struct.unpack(">I",content[offset:offset+4])[0]
            kind = content[offset+4:offset+8]
            payload = content[offset+8:offset+8+size]
            crc = struct.unpack(">I",content[offset+8+size:offset+12+size])[0]
            if crc != binascii.crc32(kind+payload)&0xffffffff:
                return False
            if kind == b"IHDR":
                width,height = struct.unpack(">II",payload[:8])
            if kind == b"IDAT":
                image_data += payload
            offset += size+12
        return width > 0 and height > 0 and len(zlib.decompress(image_data)) == height*(width+1)
    except (ValueError,struct.error,zlib.error):
        return False
