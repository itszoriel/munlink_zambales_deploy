"""Generic admin audit log model.

Tracks admin and system actions across entities (users, benefits, requests,
issues, items, announcements, etc.). Intended for unified audit browsing.
"""

from datetime import datetime

try:
    from apps.api import db
except Exception:  # pragma: no cover
    from __init__ import db

from sqlalchemy import Index


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    municipality_id = db.Column(db.Integer, db.ForeignKey('municipalities.id'), nullable=False)

    # e.g., 'document_request', 'benefit', 'issue', 'item', 'announcement', 'user', 'transaction'
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)

    action = db.Column(db.String(50), nullable=False)  # e.g., 'create','update','delete','status_processing'
    actor_role = db.Column(db.String(20), nullable=True)  # 'admin' | 'resident' | 'system'

    old_values = db.Column(db.JSON, nullable=True)
    new_values = db.Column(db.JSON, nullable=True)

    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_audit_muni', 'municipality_id'),
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_created_at', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'municipality_id': self.municipality_id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'action': self.action,
            'actor_role': self.actor_role,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


