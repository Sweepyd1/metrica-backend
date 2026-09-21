import asyncio
import base64
import json
import logging
import os

import httpx
from pydantic import ValidationError

from .images import extract_json, prepare_image
from .prompts import USER_PROMPT, build_progress_system_prompt, build_system_prompt
from .schemas import AiHomeworkResult, AiProgressLlmOut


logger = logging.getLogger(__name__)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
INCOMPLETE_RESPONSE_PROMPT = """Предыдущая попытка могла получиться неполной.
Ещё раз просмотри все изображения, пропусти скриншоты интерфейса и найди
математические условия и решения на остальных файлах. Сначала верни tasks.
Не более трёх заданий, трёх тренировочных примеров и пяти ошибок. Для каждого
неверного задания обязательно заполни errors. Пиши кратко."""


def _data_url(image_bytes: bytes, media_type: str) -> str:
    encoded = base64.standard_b64encode(image_bytes).decode()
    return f"data:{media_type};base64,{encoded}"


def _append_images(content: list[dict], label: str, images: list[tuple[bytes, str]]) -> None:
    if not images:
        return
    content.append({"type": "text", "text": f"{label}, изображений: {len(images)}"})
    for position, image in enumerate(images, start=1):
        content.append({"type": "text", "text": f"{label} — изображение {position}:"})
        content.append(
            {"type": "image_url", "image_url": {"url": _data_url(*image)}}
        )


async def review_homework_openai_compat(
    solution_images: list[tuple[bytes, str]],
    *,
    task_images: list[tuple[bytes, str]] | None = None,
    max_tasks: int,
) -> AiHomeworkResult:
    if max_tasks < 1:
        raise ValueError("Дневной лимит ИИ-проверки исчерпан.")
    if not solution_images:
        raise ValueError("В решении ученика нет поддерживаемых изображений.")

    prepared_solutions = [prepare_image(*image) for image in solution_images]
    prepared_tasks = [prepare_image(*image) for image in (task_images or [])]
    content: list[dict] = []
    _append_images(content, "Условие задания", prepared_tasks)
    _append_images(content, "Решение ученика", prepared_solutions)
    content.append({"type": "text", "text": USER_PROMPT})

    base_url = os.getenv("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
    api_key = os.getenv("OPENAI_COMPAT_API_KEY", "")
    model = os.getenv("AI_CHECKER_MODEL", "")
    if not base_url or not api_key or not model:
        raise RuntimeError("ИИ-провайдер не настроен.")

    payload = {
        "model": model,
        "max_tokens": 8000,
        "temperature": 0.2,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "ai_homework_result",
                "strict": False,
                "schema": AiHomeworkResult.model_json_schema(),
            },
        },
        "messages": [
            {"role": "system", "content": build_system_prompt(max_tasks)},
            {"role": "user", "content": content},
        ],
    }

    proxy = os.getenv("OUTBOUND_PROXY_URL") or None

    async def request_completion(request_payload: dict) -> httpx.Response:
        response: httpx.Response | None = None
        async with httpx.AsyncClient(timeout=600, proxy=proxy) as client:
            for attempt in range(1, 4):
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=request_payload,
                )
                if response.status_code not in RETRYABLE_STATUS_CODES or attempt == 3:
                    break
                await asyncio.sleep(5 * attempt)

        if response is None or not response.is_success:
            status_code = response.status_code if response is not None else "unknown"
            raise RuntimeError(f"ИИ-провайдер вернул ошибку {status_code}.")
        return response

    def parse_response(
        response: httpx.Response,
    ) -> tuple[AiHomeworkResult | None, str | None]:
        try:
            body = response.json()
            choice = body["choices"][0]
            raw = choice["message"]["content"]
            result = AiHomeworkResult.model_validate(extract_json(raw))
            return result, choice.get("finish_reason")
        except (json.JSONDecodeError, ValidationError, KeyError, TypeError, ValueError):
            return None, None

    response = await request_completion(payload)
    result, finish_reason = parse_response(response)
    incomplete_task_details = bool(result) and any(
        not task.is_correct and not task.errors for task in result.tasks
    )
    needs_retry = (
        result is None
        or finish_reason == "length"
        or (not result.tasks and bool(prepared_tasks) and bool(prepared_solutions))
        or incomplete_task_details
    )
    if needs_retry:
        retry_payload = {
            **payload,
            "messages": [
                payload["messages"][0],
                {
                    "role": "user",
                    "content": [
                        *content,
                        {"type": "text", "text": INCOMPLETE_RESPONSE_PROMPT},
                    ],
                },
            ],
        }
        response = await request_completion(retry_payload)
        result, _ = parse_response(response)

    if result is None or any(
        not task.is_correct and not task.errors for task in result.tasks
    ):
        logger.error("Модель дважды вернула ответ, не соответствующий схеме.")
        raise RuntimeError("Модель вернула некорректный результат.")

    result.tasks = result.tasks[:max_tasks]
    if result.readable and not result.tasks:
        result.readable = False
        result.quality_note = (
            result.quality_note
            or "На прикреплённых изображениях не удалось найти задания по математике."
        )
        result.summary = ""
        result.error_topics = []
        result.practice = []
    return result


async def analyze_progress_openai_compat(errors: list[dict]) -> AiProgressLlmOut:
    base_url = os.getenv("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
    api_key = os.getenv("OPENAI_COMPAT_API_KEY", "")
    model = os.getenv("AI_CHECKER_MODEL", "")
    if not base_url or not api_key or not model:
        raise RuntimeError("ИИ-провайдер не настроен.")

    payload = {
        "model": model,
        "max_tokens": 2000,
        "temperature": 0.3,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "ai_progress_report",
                "strict": False,
                "schema": AiProgressLlmOut.model_json_schema(),
            },
        },
        "messages": [
            {"role": "system", "content": build_progress_system_prompt()},
            {
                "role": "user",
                "content": json.dumps({"errors": errors}, ensure_ascii=False),
            },
        ],
    }

    proxy = os.getenv("OUTBOUND_PROXY_URL") or None

    async def request_completion() -> httpx.Response:
        response: httpx.Response | None = None
        async with httpx.AsyncClient(timeout=180, proxy=proxy) as client:
            for attempt in range(1, 4):
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                )
                if response.status_code not in RETRYABLE_STATUS_CODES or attempt == 3:
                    break
                await asyncio.sleep(5 * attempt)

        if response is None or not response.is_success:
            status_code = response.status_code if response is not None else "unknown"
            raise RuntimeError(f"ИИ-провайдер вернул ошибку {status_code}.")
        return response

    def parse_response(response: httpx.Response) -> AiProgressLlmOut | None:
        try:
            body = response.json()
            raw = body["choices"][0]["message"]["content"]
            return AiProgressLlmOut.model_validate(extract_json(raw))
        except (json.JSONDecodeError, ValidationError, KeyError, TypeError, ValueError):
            return None

    response = await request_completion()
    result = parse_response(response)
    if result is None:
        response = await request_completion()
        result = parse_response(response)

    if result is None:
        logger.error("Модель дважды вернула ответ, не соответствующий схеме сводки прогресса.")
        raise RuntimeError("Модель вернула некорректный результат.")

    return result
