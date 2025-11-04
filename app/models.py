
from .extensions import db

class Entry(db.Model):
    __tablename__ = 'entries'
    __table_args__ = (
        db.UniqueConstraint('city', 'product', name='uq_entries_city_product'),
    )

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(120), nullable=False)
    product = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    def __repr__(self):
        return f"<Entry {self.city}/{self.product}={self.price}>"
