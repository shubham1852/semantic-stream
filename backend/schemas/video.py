"""
schemas/video.py
================
Pydantic v2 response and request models for video-related API endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    """Metadata returned after a successful video upload."""

    video_id: str = Field(..., description="UUID of the stored video record.")
    filename: str = Field(..., description="Original uploaded filename.")
    duration: Optional[float] = Field(None, description="Duration in seconds.")
    fps: Optional[float] = Field(None, description="Frames per second.")
    resolution: Optional[str] = Field(None, description="WxH string e.g. '1280x720'.")
    size_mb: Optional[float] = Field(None, description="File size in megabytes.")
    uploaded_at: datetime = Field(..., description="UTC timestamp of upload.")


class VideoListItem(BaseModel):
    """Compact video record for listing endpoints."""

    video_id: str
    filename: str
    duration: Optional[float]
    size_mb: Optional[float]
    uploaded_at: datetime


class UploadResponse(BaseModel):
    """Standard response wrapper for the upload endpoint."""

    status: str
    data: VideoMetadata
    message: str
