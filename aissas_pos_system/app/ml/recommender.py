from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from app.config import DEBUG
from app.db.database import Database
from app.db.dao import OrderDAO, ProductDAO


class Recommender:
    """
    Offline 'Frequently Bought Together' recommender using past transactions.

    Features:
    - Pair-frequency analysis from order_items  (pure Python, no sklearn/cloud)
    - In-memory cache with TTL so suggestions are fast after the first build
    - suggest()            : score by association with any product list (1-item or full cart)
    - invalidate_cache()   : call after each completed sale to keep data fresh
    - get_product_names()  : batch-resolves PIDs → names (cached internally)
    """

    # Re-compute pair counts at most every 5 minutes, or when invalidated.
    CACHE_TTL_SECONDS: float = 300.0

    def __init__(self, db: Database) -> None:
        self.db = db
        self.order_dao = OrderDAO(db)
        self.prod_dao = ProductDAO(db)

        # In-memory pair-count cache  { (pid_a, pid_b): frequency }
        self._pair_cache: Optional[Dict[Tuple[int, int], int]] = None
        self._cache_time: float = 0.0

        # Product name lookup cache  { product_id: name }
        self._name_cache: Dict[int, str] = {}

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def invalidate_cache(self) -> None:
        """Force re-computation on the next suggestion request.
        Call this after every completed sale so pair counts stay up-to-date."""
        self._pair_cache = None
        self._cache_time = 0.0
        if DEBUG:
            print("[ML] Cache invalidated — will rebuild on next suggest() call.")

    def _is_cache_fresh(self) -> bool:
        return (
            self._pair_cache is not None
            and (time.monotonic() - self._cache_time) < self.CACHE_TTL_SECONDS
        )

    # ------------------------------------------------------------------
    # Core pair-count building
    # ------------------------------------------------------------------

    def _build_pair_counts(
        self, last_n_orders: int = 300
    ) -> Dict[Tuple[int, int], int]:
        """
        Build an item-pair frequency map from recent completed orders.

        Algorithm (pure Python, no external libs):
          1. Fetch order_id, product_id rows for the last N orders (completed only).
          2. Group product IDs per order into sets.
          3. For each order's item-set, emit every (a, b) pair with a < b.
          4. Accumulate pair counts.

        Results are cached in-memory (TTL = CACHE_TTL_SECONDS).
        """
        if self._is_cache_fresh():
            return self._pair_cache  # type: ignore[return-value]

        rows = self.order_dao.order_items_for_ml(last_n_orders)

        if DEBUG:
            print(f"[ML] order_items_for_ml returned {len(rows)} rows "
                  f"(last {last_n_orders} completed orders)")

        # Group: order_id → set of product_ids
        order_map: Dict[int, set[int]] = defaultdict(set)
        for r in rows:
            order_map[int(r["order_id"])].add(int(r["product_id"]))

        # Emit all canonical pairs  (smaller_id, larger_id)
        pair_counts: Dict[Tuple[int, int], int] = defaultdict(int)
        for items in order_map.values():
            items_sorted = sorted(items)
            for i in range(len(items_sorted)):
                for j in range(i + 1, len(items_sorted)):
                    pair_counts[(items_sorted[i], items_sorted[j])] += 1

        self._pair_cache = dict(pair_counts)
        self._cache_time = time.monotonic()

        if DEBUG:
            print(f"[ML] Built pair-count cache: {len(self._pair_cache)} unique pairs "
                  f"from {len(order_map)} orders.")

        return self._pair_cache

    # ------------------------------------------------------------------
    # Public suggestion API
    # ------------------------------------------------------------------

    def suggest(
        self, current_product_ids: List[int], top_n: int = 3
    ) -> List[int]:
        """
        Suggest items based on the current product selection (1 item or full cart).

        Scoring:
          For every historical pair (a, b) with count c:
            - If a is in cart and b is NOT → score[b] += c
            - If b is in cart and a is NOT → score[a] += c

        This naturally combines signals for multi-item carts:
          If the cart has [Latte, Silog], the scores for every candidate item
          accumulate from BOTH pairs, so "Fries" (associated with both) ranks highest.

        Returns top_n product IDs sorted by score descending.
        Returns [] when there are no items in the cart or no historical data.
        """
        if not current_product_ids:
            return []

        if DEBUG:
            print(f"[ML] suggest() called — cart_ids: {current_product_ids}")

        pair_counts = self._build_pair_counts()
        if not pair_counts:
            if DEBUG:
                print("[ML] No pair data available yet. Need more completed orders.")
            return []

        current = set(current_product_ids)
        scores: Dict[int, int] = defaultdict(int)

        for (a, b), c in pair_counts.items():
            if a in current and b not in current:
                scores[b] += c
            elif b in current and a not in current:
                scores[a] += c

        # Sort by score descending, return IDs only
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        result = [pid for pid, _ in ranked[:top_n]]

        if DEBUG:
            top_scored = ranked[:top_n]
            print(f"[ML] Top scores: {top_scored}")
            print(f"[ML] Suggested IDs: {result}")

        return result

    # ------------------------------------------------------------------
    # Product name resolution (for display in suggestions panel)
    # ------------------------------------------------------------------

    def get_product_names(self, product_ids: List[int]) -> Dict[int, str]:
        """
        Batch-resolve product IDs → display names.
        Uses a name cache to avoid redundant DB queries.
        """
        result: Dict[int, str] = {}

        uncached = [pid for pid in product_ids if pid not in self._name_cache]
        if uncached:
            # Fetch all active products once and populate the name cache
            try:
                all_rows = self.prod_dao.list_all_active()
                for row in all_rows:
                    self._name_cache[int(row["product_id"])] = str(row["name"])
            except Exception:
                pass

        for pid in product_ids:
            result[pid] = self._name_cache.get(pid, f"Item #{pid}")

        return result

    def get_product_price(self, product_id: int) -> float:
        """Return price of a product (for adding to cart from suggestions)."""
        try:
            all_rows = self.prod_dao.list_all_active()
            for row in all_rows:
                if int(row["product_id"]) == product_id:
                    return float(row["price"])
        except Exception:
            pass
        return 0.0
