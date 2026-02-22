from __future__ import annotations
from collections import defaultdict
from typing import Dict, List, Tuple

from app.db.database import Database
from app.db.dao import OrderDAO

class Recommender:
    """
    Offline 'Frequently Bought Together' recommender using past transactions.
    """
    def __init__(self, db: Database):
        self.db = db
        self.order_dao = OrderDAO(db)

    def build_pair_counts(self, last_n_orders: int = 200) -> Dict[Tuple[int, int], int]:
        rows = self.order_dao.order_items_for_ml(last_n_orders)
        order_map = defaultdict(set)
        for r in rows:
            order_map[int(r["order_id"])].add(int(r["product_id"]))

        pair_counts = defaultdict(int)
        for items in order_map.values():
            items = sorted(items)
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    pair_counts[(items[i], items[j])] += 1
        return pair_counts

    def suggest(self, current_product_ids: List[int], top_n: int = 3) -> List[int]:
        pair_counts = self.build_pair_counts()
        scores = defaultdict(int)

        current = sorted(set(current_product_ids))
        for (a, b), c in pair_counts.items():
            if a in current and b not in current:
                scores[b] += c
            if b in current and a not in current:
                scores[a] += c

        return [pid for pid, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]]
