from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from decimal import Decimal
from uuid import UUID


class MovieListItem(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    imdb: float
    price: float

class MovieCreate(BaseModel):
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: str
    price: Optional[Decimal] = None
    certification_id: int
    genre_ids: List[int] = []
    star_ids: List[int] = []
    director_ids: List[int] = []


class MovieRead(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: Optional[float]
    gross: Optional[float]
    description: str
    price: Optional[Decimal]
    certification_id: int
    genres: List[str]
    stars: List[str]
    directors: List[str]
    
    model_config = ConfigDict(from_attributes=True)
    

class MovieDetail(MovieListItem):
    time: int
    votes: int
    meta_score: Optional[float]
    gross: Optional[float]
    description: str
    certification: str
    genres: List[str]
    directors: List[str]
    stars: List[str]
    average_rating: Optional[float]
    likes: int
    dislikes: int


class CommentCreate(BaseModel):
    text: str
    parent_id: Optional[int] = None


class CommentRead(BaseModel):
    id: int
    user_id: int
    text: str
    created_at: datetime
    replies: list["CommentRead"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class LikeAction(BaseModel):
    is_like: bool


class RatingCreate(BaseModel):
    score: int  # 1–10

class GenreCount(BaseModel):
    id: int
    name: str
    movie_count: int


class NotificationRead(BaseModel):
    id: int
    text: str
    is_read: bool
    created_at: datetime

    class Config:
        orm_mode = True

CommentRead.update_forward_refs()