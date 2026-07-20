"""GridFS service for storing and retrieving binary files in MongoDB."""

from typing import Optional
from gridfs import GridFS
from bson import ObjectId

from app.config import logger
from app.services.database_service import connect_db


class GridFSService:
    """Service for managing binary files in MongoDB GridFS."""
    
    def __init__(self):
        """Initialize GridFS service."""
        self._fs: Optional[GridFS] = None
        self._db = None
    
    def _ensure_connection(self):
        """Ensure GridFS connection is established."""
        if self._fs is None:
            try:
                from mongoengine.connection import get_db
                
                # Ensure database is connected
                connect_db()
                
                # Get database instance
                self._db = get_db()
                self._fs = GridFS(self._db)
                logger.info("GridFS connection established")
            except Exception as e:
                logger.error(f"Failed to connect to GridFS: {e}")
                raise
    
    def save_file(
        self,
        data: bytes,
        filename: str,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Save a binary file to GridFS.
        
        Args:
            data: Binary file content
            filename: Name of the file
            content_type: MIME type of the file
            metadata: Optional metadata dictionary
            
        Returns:
            GridFS file_id (as string)
        """
        self._ensure_connection()
        
        try:
            file_id = self._fs.put(
                data,
                filename=filename,
                content_type=content_type,
                metadata=metadata or {}
            )
            logger.info(f"File saved to GridFS: {filename} (ID: {file_id})")
            return str(file_id)
        except Exception as e:
            logger.error(f"Failed to save file to GridFS: {e}")
            raise

    def save_audio_file(self, audio_data: bytes, filename: str, metadata: Optional[dict] = None) -> str:
        """Backward-compatible helper for audio file storage."""
        return self.save_file(
            data=audio_data,
            filename=filename,
            content_type="audio/wav",
            metadata=metadata,
        )

    def get_file(self, file_id: str) -> Optional[bytes]:
        """
        Retrieve a file from GridFS.
        
        Args:
            file_id: GridFS file ID (as string)
            
        Returns:
            Binary audio data or None if not found
        """
        self._ensure_connection()
        
        try:
            object_id = ObjectId(file_id)
            if not self._fs.exists(object_id):
                logger.warning(f"File not found in GridFS: {file_id}")
                return None
            grid_file = self._fs.get(object_id)
            file_data = grid_file.read()
            logger.info(f"File retrieved from GridFS: {file_id}")
            return file_data
        except Exception as e:
            logger.error(f"Failed to retrieve file from GridFS: {e}")
            return None

    def get_audio_file(self, file_id: str) -> Optional[bytes]:
        """Backward-compatible helper for audio retrieval."""
        return self.get_file(file_id)

    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from GridFS.
        
        Args:
            file_id: GridFS file ID (as string)
            
        Returns:
            True if deleted, False otherwise
        """
        self._ensure_connection()
        
        try:
            object_id = ObjectId(file_id)
            
            if self._fs.exists(object_id):
                self._fs.delete(object_id)
                logger.info(f"File deleted from GridFS: {file_id}")
                return True
            else:
                logger.warning(f"File not found for deletion: {file_id}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete file from GridFS: {e}")
            return False

    def delete_audio_file(self, file_id: str) -> bool:
        """Backward-compatible helper for audio deletion."""
        return self.delete_file(file_id)
    
    def file_exists(self, file_id: str) -> bool:
        """
        Check if audio file exists in GridFS.
        
        Args:
            file_id: GridFS file ID (as string)
            
        Returns:
            True if exists, False otherwise
        """
        self._ensure_connection()
        
        try:
            object_id = ObjectId(file_id)
            return self._fs.exists(object_id)
        except Exception:
            return False


# Global GridFS service instance
gridfs_service = GridFSService()
