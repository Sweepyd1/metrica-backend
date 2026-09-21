import json
import re
from io import BytesIO

import pillow_heif
from json_repair import repair_json
from PIL import Image


MAX_IMAGE_BYTES = 5 * 1024 * 1024
SUPPORTED_MEDIA_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
HEIC_MEDIA_TYPES = {"image/heic", "image/heif"}

pillow_heif.register_heif_opener()


class ImageTooLargeError(ValueError):
    pass


class UnsupportedImageError(ValueError):
    pass


def prepare_image(image_bytes: bytes, media_type: str) -> tuple[bytes, str]:
    normalized_type = media_type.lower().split(";", 1)[0].strip()
    if normalized_type in HEIC_MEDIA_TYPES:
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception as error:
            raise UnsupportedImageError("Не удалось прочитать HEIC/HEIF-файл.") from error
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        image_bytes = buffer.getvalue()
        normalized_type = "image/jpeg"

    if normalized_type not in SUPPORTED_MEDIA_TYPES:
        raise UnsupportedImageError(
            "ИИ-проверка поддерживает JPEG, PNG, WebP, GIF, HEIC и HEIF."
        )
    if not image_bytes:
        raise UnsupportedImageError("Файл изображения пуст.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ImageTooLargeError("Одно изображение не должно превышать 5 МБ.")
    return image_bytes, normalized_type


def extract_json(text: str) -> dict:
    normalized = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", normalized, re.DOTALL)
    if fenced:
        normalized = fenced.group(1).strip()
    if not normalized.startswith("{"):
        start, end = normalized.find("{"), normalized.rfind("}")
        if start != -1 and end > start:
            normalized = normalized[start : end + 1]
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        payload = repair_json(normalized, return_objects=True)
    if not isinstance(payload, dict):
        raise json.JSONDecodeError("Ожидался JSON-объект", normalized, 0)
    return payload
