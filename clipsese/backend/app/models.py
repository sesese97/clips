from typing import Literal
from pydantic import BaseModel, Field


class Crop(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)


class RenderRequest(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    layout: Literal["one_media", "two_cameras", "two_media"]
    camera1: Crop
    camera2: Crop | None = None
    content: Crop | None = None
    media_id: str | None = None
    media_fit: Literal["contain", "cover"] = "contain"
    media_zoom: float = Field(default=1.0, ge=0.5, le=2.5)
    media_x: float = Field(default=0.0, ge=-1.0, le=1.0)
    media_y: float = Field(default=0.0, ge=-1.0, le=1.0)


class SearchRequest(BaseModel):
    mode: Literal["keyword", "theme"]
    query: str = Field(min_length=1, max_length=240)
    max_results: int = Field(default=8, ge=1, le=20)
