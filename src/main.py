from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

from config_loader import load_yaml, BASE_DIR
from dart import OpenDartClient
from news import google_news_rss
from scoring import score_event
from telegram_notify import send_telegram, format_message
from utils import load_json, save_json, text_hash, normalize_title, prune_timestamp_map


DATA_DIR = BASE_DIR / "data"
STATE_PATH = DATA_DIR / "state.json"


def load_state():
    state = load_json(STATE_PATH, {"seen": {}, "last_run": None})
    if "seen" not in state:
        state["seen"] = {}
    return state


def save_state(state, retention_days: int):
    state["seen"] = prune_timestamp_map(state.get("seen", {}), retention_days)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_json(STATE_PATH, state)


def was_recently_sent(state, dedup_key: str, retention_days: int) -> bool:
    sent_at = state.get("seen", {}).get(dedup_key)
    if not sent_at:
        return False
    try:
        prev = datetime.fromisoformat(sent_at)
    except Exception:
        return False
    return datetime.now(timezone.utc) - prev < timedelta(days=retention_days)


def mark_seen(state, dedup_key: str):
    state.setdefault("seen", {})[dedup_key] = datetime.now(timezone.utc).isoformat()


def make_dedup_key(company_name: str, event: dict) -> str:
    source = event.get("source", "")
    if source == "DART":
        base = event.get("url", "") or event.get("title", "")
    else:
        base = normalize_title(event.get("title", ""))
    return text_hash(f"{company_name}|{source}|{base}")


def collect_events(companies: list[dict], rules: dict):
    events: list[tuple[dict, dict]] = []
    seen_urls: set[str] = set()
    seen_news_keys: set[str] = set()
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
                news = google_news_rss(
                    query,
                    limit=rules.get("news_limit_per_query", 5),
                    max_age_hours=rules.get("news_max_age_hours", 36),
                )
                for item in news:
                    item["company"] = company_name
                    news_key = text_hash(f"{company_name}|{normalize_title(item.get('title', ''))}")
                    if news_key in seen_news_keys:
                        continue
                    seen_news_keys.add(news_key)
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

    retention_days = rules.get("seen_retention_days", 14)
    collected = collect_events(companies_cfg["companies"], rules)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    sent = 0
    kept = 0
    skipped_seen = 0

    for company, event in collected:
        dedup_key = make_dedup_key(company["name"], event)
        if was_recently_sent(state, dedup_key, retention_days):
            skipped_seen += 1
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

    save_state(state, retention_days)
    print({
        "collected": len(collected),
        "kept": kept,
        "sent": sent,
        "skipped_seen": skipped_seen,
        "dry_run": args.dry_run,
    })


if __name__ == "__main__":
    main()
