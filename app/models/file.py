"""MongoDB model for uploaded and generated chat files."""

from datetime import datetime
from typing import Any, Dict

from mongoengine import DateTimeField, DictField, Document, IntField, StringField


class ChatFile(Document):
    """Persisted metadata for a user-owned file used in chat."""

    meta = {
        "collection": "chat_files",
        "indexes": [
            "user_id",
            "created_at",
            "file_type",
            ("user_id", "created_at"),
        ],
    }

    user_id = StringField(required=True, max_length=255)
    filename = StringField(required=True, max_length=255)
    mime_type = StringField(required=True, max_length=255)
    size = IntField(required=True, min_value=0)
    storage_path = StringField(max_length=1024)
    gridfs_file_id = StringField(required=True, max_length=255)
    file_type = StringField(required=True, max_length=50)
    parsed_content = StringField()
    metadata = DictField(default=dict)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size": self.size,
            "storage_path": self.storage_path,
            "gridfs_file_id": self.gridfs_file_id,
            "file_type": self.file_type,
            "parsed_content": self.parsed_content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
