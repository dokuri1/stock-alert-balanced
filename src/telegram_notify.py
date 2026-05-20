from __future__ import annotations

import html
import requests


def format_message(company: str, scored) -> str:
    e = scored.event
    reason = ", ".join(scored.reason)
    positives = ", ".join(scored.matched_positive[:5]) or "없음"
    return (
        f"<b>[{html.escape(company)}]</b> {html.escape(scored.grade)}\n"
        f"<b>제목</b> {html.escape(e.get('title', ''))}\n"
        f"<b>소스</b> {html.escape(e.get('source', ''))}\n"
        f"<b>점수</b> {scored.score}\n"
        f"<b>포지티브</b> {html.escape(positives)}\n"
        f"<b>사유</b> {html.escape(reason)}\n"
        f"<a href=\"{html.escape(e.get('url', ''))}\">원문 보기</a>"
    )


def send_telegram(bot_token: str, chat_id: str, message: str, timeout: int = 20):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()
