"""MongoDB models for legal research sources and cached TanzLII documents."""

from datetime import datetime
from typing import Any, Dict, Optional

from mongoengine import DateTimeField, DictField, Document, IntField, ListField, StringField


class LegalDocument(Document):
    """Cached legal material fetched from TanzLII."""

    meta = {
        "collection": "legal_documents",
        "indexes": [
            "source_url",
            "normalized_url",
            "collection",
            "source_type",
            "court",
            "nature",
            "year",
            "document_date",
            "last_synced_at",
            {"fields": ["normalized_url"], "unique": True, "name": "uniq_legal_normalized_url"},
        ],
    }

    source_url = StringField(required=True)
    normalized_url = StringField(required=True)
    source_type = StringField(default="tanzlii")
    collection = StringField(
        required=True,
        choices=[
            "judgments",
            "legislation",
            "gazettes",
            "secondary_sources",
            "practice_essentials",
            "regional_law",
            "other",
        ],
    )
    title = StringField(required=True)
    akn_uri = StringField()
    citation = StringField()
    court = StringField()
    nature = StringField()
    jurisdiction = StringField(default="tz")
    language = StringField(default="en")
    year = IntField()
    document_date = DateTimeField()
    expression_date = DateTimeField()
    status_labels = ListField(StringField(), default=list)
    text_content = StringField()
    summary = StringField()
    metadata = DictField(default=dict)
    source_links = ListField(StringField(), default=list)
    section_chunks = ListField(DictField(), default=list)
    last_synced_at = DateTimeField(default=datetime.utcnow)
    last_seen_at = DateTimeField(default=datetime.utcnow)
    fetch_error = StringField()

    def save(self, *args, **kwargs):
        """Keep timestamps fresh on every write."""
        self.last_seen_at = datetime.utcnow()
        if not self.last_synced_at:
            self.last_synced_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    def to_source_dict(self) -> Dict[str, Any]:
        """Serialize the cached legal source for downstream use."""
        return {
            "id": str(self.id),
            "title": self.title,
            "url": self.source_url,
            "collection": self.collection,
            "citation": self.citation,
            "court": self.court,
            "nature": self.nature,
            "year": self.year,
            "document_date": self.document_date.isoformat() if self.document_date else None,
            "expression_date": self.expression_date.isoformat() if self.expression_date else None,
            "status_labels": self.status_labels,
            "summary": self.summary,
            "has_text": bool(self.text_content),
            "fetch_error": self.fetch_error,
        }

    @classmethod
    def upsert_source(
        cls,
        normalized_url: str,
        defaults: Dict[str, Any],
    ) -> "LegalDocument":
        """Create or update a cached legal source."""
        document = cls.objects(normalized_url=normalized_url).first()
        if document is None:
            document = cls(normalized_url=normalized_url, **defaults)
        else:
            for key, value in defaults.items():
                setattr(document, key, value)
        document.last_synced_at = datetime.utcnow()
        document.fetch_error = defaults.get("fetch_error")
        document.save()
        return document

    @classmethod
    def find_cached(
        cls,
        query: str,
        collection: Optional[str] = None,
        limit: int = 5,
    ) -> list["LegalDocument"]:
        """Search cached documents by title/content to soften live fetch failures."""
        queryset = cls.objects
        if collection:
            queryset = queryset(collection=collection)

        title_matches = list(queryset(title__icontains=query).order_by("-last_seen_at")[:limit])
        if len(title_matches) >= limit:
            return title_matches

        text_matches = list(
            queryset(text_content__icontains=query, id__nin=[doc.id for doc in title_matches])
            .order_by("-last_seen_at")[: max(limit - len(title_matches), 0)]
        )
        return title_matches + text_matches
