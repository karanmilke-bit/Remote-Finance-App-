"""
PulseFinance Supabase Sync Bridge (Desktop GUI connected to Cloud Supabase).
Works with CustomTkinter and syncs with the same Supabase database deployed on Vercel.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

SUPABASE_URL = "https://lggevcvmtxpngeilsnba.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxnZ2V2Y3ZtdHhwbmdlaWxzbmJhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ4NzA2MzAsImV4cCI6MjEwMDQ0NjYzMH0.r-_pzew2NV_msvj92Y6b29GFaQkZ9LmoJ9S9sAdHvcI"


class SupabaseFinanceClient:
    """REST Client for Supabase public.finance_transactions table using standard urllib."""

    def __init__(self, url: str = SUPABASE_URL, key: str = SUPABASE_KEY):
        self.endpoint = f"{url.rstrip('/')}/rest/v1/finance_transactions"
        self.key = key
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def fetch_all_transactions(self) -> List[Dict[str, Any]]:
        req = urllib.request.Request(
            f"{self.endpoint}?select=*&order=transaction_date.desc",
            headers=self.headers,
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            print(f"[Supabase Error] Failed to fetch: {e}")
            return []

    def insert_transaction(
        self,
        title: str,
        category: str,
        amount: float,
        transaction_date: str,
        is_income: bool,
        note: str = "",
    ) -> Optional[Dict[str, Any]]:
        payload = {
            "title": title or category,
            "category": category,
            "amount": float(amount),
            "transaction_date": transaction_date,
            "is_income": is_income,
            "note": note,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=data, headers=self.headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res[0] if res else None
        except urllib.error.URLError as e:
            print(f"[Supabase Error] Failed to insert: {e}")
            return None

    def update_transaction(self, tx_id: str, updates: Dict[str, Any]) -> bool:
        url = f"{self.endpoint}?id=eq.{urllib.parse.quote(tx_id)}"
        data = json.dumps(updates).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self.headers, method="PATCH")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 204)
        except urllib.error.URLError as e:
            print(f"[Supabase Error] Failed to update: {e}")
            return False

    def delete_transaction(self, tx_id: str) -> bool:
        url = f"{self.endpoint}?id=eq.{urllib.parse.quote(tx_id)}"
        req = urllib.request.Request(url, headers=self.headers, method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 204)
        except urllib.error.URLError as e:
            print(f"[Supabase Error] Failed to delete: {e}")
            return False


if __name__ == "__main__":
    client = SupabaseFinanceClient()
    txs = client.fetch_all_transactions()
    print(f"Connected to Supabase! Successfully fetched {len(txs)} transactions.")
    for t in txs[:3]:
        sign = "+" if t.get("is_income") else "-"
        print(f" - [{t.get('transaction_date')}] {t.get('category')}: {sign}₹{t.get('amount')} ({t.get('title')})")
