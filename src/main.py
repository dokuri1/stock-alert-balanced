from __future__ import annotations

import argparse
import os

from config_loader import load_yaml, BASE_DIR
from dart import OpenDartClient
from news import google_news_rss
from scoring import score_event
from telegram_notify import send_telegram, format_message
from utils import load_json, save_json, text_hash


DATA_DIR = BASE_DIR / "data"
STATE_PATH = DATA_DIR / "state.json"


def load_state():
    return load_json(STATE_PATH, {"seen": {}, "last_run": None})


def save_state(state):
    save_json(STATE_PATH, state)


def should_skip(state, dedup_key: str, cooldown_minutes: int) -> bool:
    from datetime import datetime, timedelta, timezone

    seen_at = state["seen"].get(dedup_key)
    if not seen_at:
        return False
    prev = datetime.fromisoformat(seen_at)
    return datetime.now(timezone.utc) - prev < timedelta(minutes=cooldown_minutes)


def mark_seen(state, dedup_key: str):
    from datetime import datetime, timezone

    state["seen"][dedup_key] = datetime.now(timezone.utc).isoformat()


def collect_events(companies: list[dict], rules: dict):
    events: list[tuple[dict, dict]] = []
    seen_urls: set[str] = set()
    dart_key = os.getenv("OPENDART_API_KEY", "").strip()
    dart_client = OpenDartClient(dart_key) if dart_key else None

    for company in companies:
        company_name = company["name"]

        if dart_client:
            try:
                corp_code = dart_client.resolve_corp_code(company.get("dart_name", company_name))
                if corp_code:
                    disclosures = dart_client.list_disclosures(
                        corp_code=corp_code,
                        lookback_days=rules.get("lookback_days", 2),
                    )
                    for item in disclosures:
                        item["company"] = company_name
                        if item["url"] not in seen_urls:
                            seen_urls.add(item["url"])
                            events.append((company, item))
            except Exception as e:
                print(f"[WARN] DART skipped for {company_name}: {e}")

        queries = company.get("news_queries") or [company_name]
        for query in queries:
            try:
                news = google_news_rss(query, limit=rules.get("news_limit_per_query", 5))
                for item in news:
                    item["company"] = company_name
                    if item["url"] not in seen_urls:
                        seen_urls.add(item["url"])
                        events.append((company, item))
            except Exception as e:
                print(f"[WARN] NEWS skipped for {company_name} / {query}: {e}")

    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    companies_cfg = load_yaml("companies.yaml")
    rules = load_yaml("rules.yaml")
    state = load_state()

    cooldown = rules.get("cooldown_minutes", 180)
    collected = collect_events(companies_cfg["companies"], rules)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    sent = 0
    kept = 0

    for company, event in collected:
        dedup_key = text_hash(f"{company['name']}|{event.get('title','')}|{event.get('url','')}")
        if should_skip(state, dedup_key, cooldown):
            continue

        scored = score_event(event, rules, company)
        if scored.grade not in {"P1", "P2"}:
            continue

        kept += 1
        print(f"[{company['name']}] {scored.grade} {scored.score} :: {event['title']}")

        if not args.dry_run and bot_token and chat_id:
            msg = format_message(company["name"], scored)
            try:
                send_telegram(bot_token, chat_id, msg)
                sent += 1
                mark_seen(state, dedup_key)
            except Exception as e:
                print(f"[WARN] Telegram failed for {company['name']}: {e}")
        else:
            mark_seen(state, dedup_key)

    save_state(state)
    print({"collected": len(collected), "kept": kept, "sent": sent, "dry_run": args.dry_run})


if __name__ == "__main__":
    main()
