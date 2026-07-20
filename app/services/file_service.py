"""Storage and retrieval service for uploaded and generated chat files."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import UploadFile

from app.config import MAX_UPLOAD_SIZE_MB
from app.models.file import ChatFile
from app.services.document_extraction import document_extraction_service
from app.services.gridfs_service import gridfs_service
from app.utils.error_handler import create_400_error, create_403_error, create_404_error


class FileService:
    """Manage user-owned files for chat upload and document generation."""

    ALLOWED_EXTENSIONS = {
        ".txt": "text",
        ".md": "text",
        ".markdown": "text",
        ".json": "json",
        ".csv": "spreadsheet",
        ".xlsx": "spreadsheet",
        ".xls": "spreadsheet",
        ".pdf": "pdf",
        ".docx": "document",
        ".pptx": "presentation",
    }

    def upload_file(self, user_id: str, upload: UploadFile) -> dict:
        filename = upload.filename or "uploaded-file"
        extension = Path(filename).suffix.lower()
        if extension not in self.ALLOWED_EXTENSIONS:
            raise create_400_error(
                "Unsupported file type. Allowed formats: txt, md, json, csv, xlsx, xls, pdf, docx, pptx"
            )

        file_bytes = upload.file.read()
        upload.file.seek(0)
        size = len(file_bytes)
        max_size_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if size > max_size_bytes:
            raise create_400_error(f"File exceeds maximum upload size of {MAX_UPLOAD_SIZE_MB} MB")

        parsed_content = self._extract_content_from_bytes(file_bytes, filename, upload.content_type)
        mime_type = upload.content_type or self._guess_mime(extension)
        gridfs_file_id = gridfs_service.save_file(
            data=file_bytes,
            filename=filename,
            content_type=mime_type,
            metadata={"user_id": user_id, "origin": "upload"},
        )
        chat_file = ChatFile(
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            size=size,
            storage_path="",
            gridfs_file_id=gridfs_file_id,
            file_type=self.ALLOWED_EXTENSIONS[extension],
            parsed_content=parsed_content,
            metadata={
                "origin": "upload",
                "summary": self._build_summary(parsed_content, filename),
            },
        )
        chat_file.save()
        chat_file.metadata["download_url"] = self.get_download_url(str(chat_file.id))
        chat_file.save()
        return self.serialize_file(chat_file)

    def create_generated_file(
        self,
        user_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
        file_type: str,
        parsed_content: str = "",
        metadata: dict | None = None,
    ) -> dict:
        gridfs_file_id = gridfs_service.save_file(
            data=content,
            filename=filename,
            content_type=mime_type,
            metadata={"user_id": user_id, "origin": "generated"},
        )

        chat_file = ChatFile(
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            size=len(content),
            storage_path="",
            gridfs_file_id=gridfs_file_id,
            file_type=file_type,
            parsed_content=parsed_content,
            metadata={
                "origin": "generated",
                "summary": self._build_summary(parsed_content, filename),
                **(metadata or {}),
            },
        )
        chat_file.save()
        chat_file.metadata["download_url"] = self.get_download_url(str(chat_file.id))
        chat_file.save()
        return self.serialize_file(chat_file)

    def list_files(self, user_id: str, limit: int = 50) -> list[dict]:
        files = ChatFile.objects(user_id=user_id).order_by("-created_at").limit(limit)
        return [self.serialize_file(file) for file in files]

    def get_file(self, user_id: str, file_id: str) -> ChatFile:
        chat_file = ChatFile.objects(id=file_id).first()
        if not chat_file:
            raise create_404_error("File not found")
        if chat_file.user_id != user_id:
            raise create_403_error("You do not have access to this file")
        return chat_file

    def get_file_payload(self, user_id: str, file_id: str) -> dict:
        return self.serialize_file(self.get_file(user_id, file_id))

    def get_file_text(self, user_id: str, file_id: str, max_chars: int = 12_000) -> str:
        chat_file = self.get_file(user_id, file_id)
        text = (chat_file.parsed_content or "").strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "\n...[truncated]"

    def get_file_bytes(self, user_id: str, file_id: str) -> bytes:
        chat_file = self.get_file(user_id, file_id)
        data = gridfs_service.get_file(chat_file.gridfs_file_id)
        if data is None:
            raise create_404_error("Stored file content was not found")
        return data

    def serialize_file(self, chat_file: ChatFile) -> dict:
        data = chat_file.to_dict()
        data["download_url"] = self.get_download_url(data["id"])
        data["summary"] = data.get("metadata", {}).get("summary") or self._build_summary(
            data.get("parsed_content") or "",
            data["filename"],
        )
        return data

    def build_attachment_payloads(self, user_id: str, file_ids: list[str]) -> list[dict]:
        return [self.serialize_file(self.get_file(user_id, file_id)) for file_id in file_ids]

    def get_download_url(self, file_id: str) -> str:
        return f"/files/{file_id}/download"

    def _guess_mime(self, extension: str) -> str:
        return {
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".markdown": "text/markdown",
            ".json": "application/json",
            ".csv": "text/csv",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }.get(extension, "application/octet-stream")

    def _build_summary(self, parsed_content: str, filename: str, max_chars: int = 240) -> str:
        if not parsed_content:
            return f"{filename} uploaded successfully."
        summary = " ".join(parsed_content.split())
        if len(summary) <= max_chars:
            return summary
        return summary[:max_chars].rstrip() + "..."

    def _extract_content_from_bytes(self, file_bytes: bytes, filename: str, mime_type: str | None) -> str:
        suffix = Path(filename).suffix or ".tmp"
        with NamedTemporaryFile(suffix=suffix, delete=True) as temp_file:
            temp_file.write(file_bytes)
            temp_file.flush()
            return document_extraction_service.extract(Path(temp_file.name), mime_type)


file_service = FileService()
