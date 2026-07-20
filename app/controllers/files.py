"""File upload and download endpoints for chat documents."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from io import BytesIO

from app.models.auth import User
from app.services.file_service import file_service
from app.utils.auth_utils import get_current_active_user
from app.utils.error_handler import handle_http_errors

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", summary="Upload a chat document")
@handle_http_errors("Error uploading file")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    return file_service.upload_file(str(current_user.id), file)


@router.get("", summary="List uploaded and generated files")
@handle_http_errors("Error listing files")
async def list_files(
    current_user: User = Depends(get_current_active_user),
) -> dict:
    files = file_service.list_files(str(current_user.id))
    return {"files": files, "count": len(files)}


@router.get("/{file_id}", summary="Get file metadata")
@handle_http_errors("Error getting file")
async def get_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
) -> dict:
    return file_service.get_file_payload(str(current_user.id), file_id)


@router.get("/{file_id}/download", summary="Download a file")
@handle_http_errors("Error downloading file")
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    chat_file = file_service.get_file(str(current_user.id), file_id)
    file_bytes = file_service.get_file_bytes(str(current_user.id), file_id)
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=chat_file.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{chat_file.filename}"'
        },
    )
