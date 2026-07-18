"""Lossless JPEG metadata stripping for already-uploaded post images.

Clients now re-encode photos before uploading, so nothing uploaded going
forward carries EXIF (issue #346). Images uploaded before that fix still sit in
the S3 buckets with their original metadata — including GPS coordinates — and
this module powers the `strip_image_metadata` management command that cleans
them in place.

The strip works at the JPEG segment level rather than by re-encoding: the
entropy-coded pixel data is copied verbatim, so the operation is lossless.
Metadata-bearing segments (EXIF/XMP in APP1, IPTC/Photoshop in APP13, other
vendor APPn blocks, and COM comments) are dropped, and anything after the EOI
marker (e.g. vendor "motion photo" trailers, which can embed video with its own
location data) is truncated. Segments a decoder needs to render the image
correctly — JFIF (APP0), ICC color profiles (APP2), and the Adobe color
transform (APP14) — are kept. If the original had an EXIF Orientation tag, a
minimal EXIF block holding only that tag is re-inserted so the photo still
displays upright.
"""

import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)

# EXIF tag 274: Orientation.
_ORIENTATION_TAG = 0x0112

# APPn segments that are required to decode/render the image correctly and
# carry no personal data: JFIF (APP0), ICC color profile (APP2), Adobe color
# transform (APP14). Every other APPn — EXIF/XMP (APP1), IPTC (APP13), vendor
# blocks — is metadata and gets dropped, as do COM (0xFE) comment segments.
_KEPT_APP_MARKERS = frozenset({0xE0, 0xE2, 0xEE})


def _is_jpeg(data):
    return len(data) >= 2 and data[0] == 0xFF and data[1] == 0xD8


def _orientation(data):
    """The EXIF Orientation of the image, or None if absent/upright/unreadable."""
    try:
        orientation = Image.open(io.BytesIO(data)).getexif().get(_ORIENTATION_TAG)
    except Exception:
        return None
    # 1 is "upright" (the default), so only 2..8 are worth preserving.
    if isinstance(orientation, int) and 2 <= orientation <= 8:
        return orientation
    return None


def _orientation_app1(orientation):
    """A raw APP1 segment holding an EXIF block with only the Orientation tag."""
    exif = Image.Exif()
    exif[_ORIENTATION_TAG] = orientation
    payload = exif.tobytes()  # b'Exif\x00\x00' + TIFF data
    return b'\xff\xe1' + (len(payload) + 2).to_bytes(2, 'big') + payload


def _rebuild(data, orientation):
    """Copy `data` segment by segment, dropping metadata segments and anything
    after EOI. Raises ValueError on malformed input."""
    out = bytearray(b'\xff\xd8')
    if orientation is not None:
        out += _orientation_app1(orientation)

    i = 2
    n = len(data)
    while i < n - 1:
        if data[i] != 0xFF:
            raise ValueError(f"expected a marker at offset {i}")
        marker = data[i + 1]
        if marker == 0xFF:  # padding fill byte before a marker
            i += 1
            continue
        if marker == 0xD9:  # EOI — done; drop any trailer after it.
            out += b'\xff\xd9'
            return bytes(out)
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:  # standalone markers
            out += data[i:i + 2]
            i += 2
            continue

        if i + 4 > n:
            raise ValueError("truncated segment header")
        length = int.from_bytes(data[i + 2:i + 4], 'big')
        if length < 2 or i + 2 + length > n:
            raise ValueError(f"bad segment length at offset {i}")
        segment = data[i:i + 2 + length]
        i += 2 + length

        if (0xE0 <= marker <= 0xEF and marker not in _KEPT_APP_MARKERS) or marker == 0xFE:
            continue  # metadata segment — drop it

        out += segment
        if marker == 0xDA:  # SOS — entropy-coded data follows the header.
            start = i
            # Within entropy data 0xFF is always followed by a stuffed 0x00 or
            # a restart marker (0xD0-0xD7); anything else is a real marker
            # (the next scan of a progressive JPEG, or EOI) ending the run.
            while i < n - 1 and not (
                data[i] == 0xFF
                and data[i + 1] != 0x00
                and data[i + 1] != 0xFF
                and not 0xD0 <= data[i + 1] <= 0xD7
            ):
                i += 1
            out += data[start:i]

    raise ValueError("no EOI marker found")


def strip_jpeg_metadata(data):
    """Return `data` with all metadata removed except the EXIF Orientation tag.

    Lossless: the compressed pixel data is copied byte-for-byte, so image
    quality is untouched. If the original carried an EXIF Orientation, a
    minimal EXIF block holding only that tag is kept so the image still
    displays upright. Returns the input unchanged (and logs) if it is not a
    JPEG or cannot be parsed; callers can compare the result to the input to
    tell whether anything was stripped.
    """
    if not _is_jpeg(data):
        return data
    try:
        return _rebuild(data, _orientation(data))
    except ValueError:
        logger.warning("Could not parse JPEG to strip metadata; leaving it unchanged.", exc_info=True)
        return data
