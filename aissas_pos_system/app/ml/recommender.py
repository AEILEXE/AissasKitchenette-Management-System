"""
app/ml/recommender.py
Hybrid offline recommender for the POS suggestion panel.

Strategy
--------
  LOW_DATA  (completed orders < PAIR_THRESHOLD):
    1. Top-selling products from completed order history  (popularity signal)
    2. Same-category products as items already in cart    (add-on signal)
    Excludes items already in the cart.

  SUFFICIENT_DATA  (completed orders >= PAIR_THRESHOLD):
    Pair-frequency association scoring (existing algorithm).
    Falls back to popularity signal when pair scores are all 0.

No external libraries required (pure Python + SQLite).
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from app.db.database import Database
from app.db.dao import OrderDAO, ProductDAO


PAIR_THRESHOLD = 10


class Recommender:
    CACHE_TTL_SECONDS: float = 300.0

    def __init__(self, db: Database) -> None:
        self.db = db
        self.order_dao = OrderDAO(db)
        self.prod_dao = ProductDAO(db)

        self._pair_cache: Optional[Dict[Tuple[int, int], int]] = None
        self._cache_time: float = 0.0
        self._name_cache: Dict[int, str] = {}
        self._price_cache: Dict[int, float] = {}

    def invalidate_cache(self) -> None:
        self._pair_cache = None
        self._cache_time = 0.0
        self._name_cache.clear()
        self._price_cache.clear()

    def _is_cache_fresh(self) -> bool:
        return (
            self._pair_cache is not None
            and (time.monotonic() - self._cache_time) < self.CACHE_TTL_SECONDS
        )

    def _load_product_catalog(self) -> None:
        if self._name_cache:
            return
        try:
            rows = self.prod_dao.list_all_active()
            for row in rows:
                pid = int(row["product_id"])
                self._name_cache[pid] = str(row["name"])
                self._price_cache[pid] = float(row["price"])
        except Exception:
            pass

    def _get_category_ids(self, product_ids: List[int]) -> Set[int]:
        if not product_ids:
            return set()
        try:
            placeholders = ",".join("?" * len(product_ids))
            rows = self.db.fetchall(
                f"SELECT id, category_id FROM products WHERE id IN ({placeholders});",
                tuple(product_ids),
            )
            return {int(r["category_id"]) for r in rows if r["category_id"] is not None}
        except Exception:
            return set()

    def _same_category_candidates(self, cart_ids: List[int], exclude: Set[int]) -> List[int]:
        cat_ids = self._get_category_ids(cart_ids)
        if not cat_ids:
            return []
        try:
            cp = ",".join("?" * len(cat_ids))
            ep = ",".join("?" * len(exclude)) if exclude else "0"
            rows = self.db.fetchall(
                f"SELECT p.id AS product_id FROM products p "
                f"WHERE p.category_id IN ({cp}) AND p.active=1 "
                f"AND p.id NOT IN ({ep}) ORDER BY p.name;",
                tuple(cat_ids) + tuple(exclude),
            )
            return [int(r["product_id"]) for r in rows]
        except Exception:
            return []

    def _top_sellers(self, top_n: int, exclude: Set[int]) -> List[int]:
        try:
            rows = self.prod_dao.top_sellers(limit=top_n + len(exclude) + 5)
            result = []
            for row in rows:
                pid = int(row["product_id"])
                if pid not in exclude:
                    result.append(pid)
                    if len(result) >= top_n:
                        break
            return result
        except Exception:
            return []

    def _build_pair_counts(self, last_n_orders: int = 300) -> Dict[Tuple[int, int], int]:
        if self._is_cache_fresh():
            return self._pair_cache  # type: ignore[return-value]
        rows = self.order_dao.order_items_for_ml(last_n_orders)
        order_map: Dict[int, set] = defaultdict(set)
        for r in rows:
            order_map[int(r["order_id"])].add(int(r["product_id"]))
        pair_counts: Dict[Tuple[int, int], int] = defaultdict(int)
        for items in order_map.values():
            items_sorted = sorted(items)
            for i in range(len(items_sorted)):
                for j in range(i + 1, len(items_sorted)):
                    pair_counts[(items_sorted[i], items_sorted[j])] += 1
        self._pair_cache = dict(pair_counts)
        self._cache_time = time.monotonic()
        return self._pair_cache

    def _pair_suggest(self, current_product_ids: List[int], top_n: int) -> List[int]:
        pair_counts = self._build_pair_counts()
        if not pair_counts:
            return []
        current = set(current_product_ids)
        scores: Dict[int, int] = defaultdict(int)
        for (a, b), c in pair_counts.items():
            if a in current and b not in current:
                scores[b] += c
            elif b in current and a not in current:
                scores[a] += c
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [pid for pid, _ in ranked[:top_n]]

    def suggest(self, current_product_ids: List[int], top_n: int = 3) -> List[int]:
        """
        Hybrid suggestion:
          - Low history: top sellers + same-category add-ons
          - Sufficient history: pair-frequency with popularity fallback
        """
        if not current_product_ids:
            return []

        exclude = set(current_product_ids)
        completed_orders = self.order_dao.count_by_status("Completed")

        if completed_orders < PAIR_THRESHOLD:
            result: List[int] = []
            for pid in self._same_category_candidates(current_product_ids, exclude):
                if len(result) >= top_n:
                    break
                result.append(pid)
                exclude.add(pid)
            if len(result) < top_n:
                for pid in self._top_sellers(top_n, exclude):
                    if len(result) >= top_n:
                        break
                    result.append(pid)
            return result[:top_n]

        result = self._pair_suggest(current_product_ids, top_n)
        if not result:
            result = self._top_sellers(top_n, exclude)
        return result[:top_n]

    def get_product_names(self, product_ids: List[int]) -> Dict[int, str]:
        self._load_product_catalog()
        return {pid: self._name_cache.get(pid, f"Item #{pid}") for pid in product_ids}

    def get_product_price(self, product_id: int) -> float:
        self._load_product_catalog()
        if product_id in self._price_cache:
            return self._price_cache[product_id]
        try:
            rows = self.prod_dao.list_all_active()
            for row in rows:
                if int(row["product_id"]) == product_id:
                    return float(row["price"])
        except Exception:
            pass
        return 0.0
