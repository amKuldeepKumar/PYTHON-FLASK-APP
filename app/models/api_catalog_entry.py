from datetime import datetime

from ..extensions import db


class ApiCatalogEntry(db.Model):
    __tablename__ = "api_catalog_entries"

    PRICING_FREE = "free"
    PRICING_FREEMIUM = "freemium"
    PRICING_PAID = "paid"
    PRICING_ENTERPRISE = "enterprise"

    MARKET_NEW = "new"
    MARKET_EMERGING = "emerging"
    MARKET_ESTABLISHED = "established"
    MARKET_MATURE = "mature"

    RECOMMENDATION_BEST = "best_fit"
    RECOMMENDATION_RECOMMENDED = "recommended"
    RECOMMENDATION_WATCH = "watchlist"
    RECOMMENDATION_RESEARCH = "research"

    id = db.Column(db.Integer, primary_key=True)
    category_key = db.Column(db.String(40), nullable=False, index=True)
    service_key = db.Column(db.String(80), nullable=False, index=True)
    service_name = db.Column(db.String(160), nullable=False)
    provider_name = db.Column(db.String(160), nullable=False)
    provider_family = db.Column(db.String(80), nullable=True)
    pricing_tier = db.Column(db.String(20), nullable=False, default=PRICING_PAID, index=True)
    market_status = db.Column(db.String(20), nullable=False, default=MARKET_ESTABLISHED, index=True)
    recommendation_level = db.Column(db.String(20), nullable=False, default=RECOMMENDATION_RESEARCH, index=True)
    official_url = db.Column(db.String(255), nullable=True)
    api_base_url = db.Column(db.String(255), nullable=True)
    advantage_summary = db.Column(db.Text, nullable=True)
    best_for = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_selected = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_active_candidate = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def pricing_label(self) -> str:
        return {
            self.PRICING_FREE: "Free",
            self.PRICING_FREEMIUM: "Freemium",
            self.PRICING_PAID: "Paid",
            self.PRICING_ENTERPRISE: "Enterprise",
        }.get(self.pricing_tier, (self.pricing_tier or "Unknown").replace("_", " ").title())

    @property
    def market_label(self) -> str:
        return {
            self.MARKET_NEW: "New",
            self.MARKET_EMERGING: "Emerging",
            self.MARKET_ESTABLISHED: "Established",
            self.MARKET_MATURE: "Mature",
        }.get(self.market_status, (self.market_status or "Unknown").replace("_", " ").title())

    @property
    def recommendation_label(self) -> str:
        return {
            self.RECOMMENDATION_BEST: "Best Fit",
            self.RECOMMENDATION_RECOMMENDED: "Recommended",
            self.RECOMMENDATION_WATCH: "Watchlist",
            self.RECOMMENDATION_RESEARCH: "Research",
        }.get(self.recommendation_level, (self.recommendation_level or "Unknown").replace("_", " ").title())
