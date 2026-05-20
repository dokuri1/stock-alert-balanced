from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

import requests


class OpenDartClient:
    def __init__(self, api_key: str, timeout: int = 20):
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()

    def _download_corp_codes(self):
        url = "https://opendart.fss.or.kr/api/corpCode.xml"
        resp = self.session.get(url, params={"crtfc_key": self.api_key}, timeout=self.timeout)
        resp.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        xml_name = zf.namelist()[0]
        xml_bytes = zf.read(xml_name)
        root = ET.fromstring(xml_bytes)
        rows = []
        for item in root.findall("list"):
            rows.append(
                {
                    "corp_code": (item.findtext("corp_code") or "").strip(),
                    "corp_name": (item.findtext("corp_name") or "").strip(),
                    "stock_code": (item.findtext("stock_code") or "").strip(),
                }
            )
        return rows

    def resolve_corp_code(self, corp_name: str) -> str | None:
        rows = self._download_corp_codes()
        exact = [r for r in rows if r["corp_name"] == corp_name]
        if exact:
            return exact[0]["corp_code"]
        fuzzy = [r for r in rows if corp_name in r["corp_name"]]
        return fuzzy[0]["corp_code"] if fuzzy else None

    def list_disclosures(self, corp_code: str, lookback_days: int = 3):
        end = datetime.now()
        start = end - timedelta(days=lookback_days)
        url = "https://opendart.fss.or.kr/api/list.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bgn_de": start.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "last_reprt_at": "Y",
            "page_no": 1,
            "page_count": 20,
        }
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "000":
            return []
        results = []
        for row in data.get("list", []):
            rcept_no = row.get("rcept_no", "")
            results.append(
                {
                    "source": "DART",
                    "company": row.get("corp_name", ""),
                    "title": row.get("report_nm", ""),
                    "published_at": row.get("rcept_dt", ""),
                    "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
                    "raw": row,
                }
            )
        return results
