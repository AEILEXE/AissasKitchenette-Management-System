from __future__ import annotations
from app.db.database import Database
from app.db.dao import OrderDAO

class ReportService:
    def __init__(self, db: Database):
        self.db = db
        self.order_dao = OrderDAO(db)

    def today_summary(self):
        return self.order_dao.summary_today()

    def today_best_sellers(self, limit: int = 10):
        return self.order_dao.best_sellers_today(limit)
