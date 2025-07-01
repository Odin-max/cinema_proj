import uuid
from sqlalchemy import (
    Column, Integer, String, Float, Text, DECIMAL,
    ForeignKey, UniqueConstraint, Table, DateTime
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
from pydantic import BaseModel


movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id"), primary_key=True),
)

movie_stars = Table(
    "movie_stars",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id"), primary_key=True),
    Column("star_id", ForeignKey("stars.id"), primary_key=True),
)

movie_directors = Table(
    "movie_directors",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id"), primary_key=True),
    Column("director_id", ForeignKey("directors.id"), primary_key=True),
)

class CertificationModel(Base):
    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)

    movies = relationship("MovieModel", back_populates="certification")

class CertificationCreate(BaseModel):
    name: str

class CertificationRead(BaseModel):
    id: int
    name: str
    class Config:
        orm_mode = True

class CertificationUpdate(BaseModel):
    name: str


class GenreModel(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)

    movies = relationship("MovieModel", secondary=movie_genres, back_populates="genres")

class GenreCreate(BaseModel):
    name: str

class GenreRead(BaseModel):
    id: int
    name: str
    class Config:
        orm_mode = True

class GenreUpdate(BaseModel):
    name: str


class StarModel(Base):
    __tablename__ = "stars"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)

    movies = relationship("MovieModel", secondary=movie_stars, back_populates="stars")

class StarCreate(BaseModel):
    name: str

class StarRead(BaseModel):
    id: int
    name: str
    class Config:
        orm_mode = True

class StarUpdate(BaseModel):
    name: str
    
class DirectorModel(Base):
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)

    movies = relationship("MovieModel", secondary=movie_directors, back_populates="directors")


class DirectorCreate(BaseModel):
    name: str


class DirectorRead(BaseModel):
    id: int
    name: str
    class Config:
        orm_mode = True


class DirectorUpdate(BaseModel):
    name: str


class MovieModel(Base):
    __tablename__ = "movies"
    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="uq_movie_name_year_time"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(PG_UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    name = Column(String(250), nullable=False)
    year = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)
    imdb = Column(Float, nullable=False)
    votes = Column(Integer, nullable=False)
    meta_score = Column(Float, nullable=True)
    gross = Column(Float, nullable=True)
    description = Column(Text, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=True)
    certification_id = Column(Integer, ForeignKey("certifications.id"), nullable=False)

    certification = relationship("CertificationModel", back_populates="movies")
    genres = relationship("GenreModel", secondary=movie_genres, back_populates="movies", lazy="selectin")
    stars = relationship("StarModel", secondary=movie_stars, back_populates="movies")
    directors = relationship("DirectorModel", secondary=movie_directors, back_populates="movies")

class CommentModel(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    replies = relationship(
        "CommentModel",
        backref="parent",
        remote_side=[id],
        cascade="all",
        single_parent=True,
        collection_class=list
    )
    likes = relationship("CommentLikeModel", back_populates="comment", cascade="all, delete-orphan")

class CommentLikeModel(Base):
    __tablename__ = "comment_likes"

    comment_id = Column(Integer, ForeignKey("comments.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    comment = relationship("CommentModel", back_populates="likes")

class MovieLikeModel(Base):
    __tablename__ = "movie_likes"

    movie_id = Column(Integer, ForeignKey("movies.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    is_like = Column(Integer, nullable=False)  # 1=like, 0=dislike
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class FavoriteModel(Base):
    __tablename__ = "favorites"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    movie_id = Column(Integer, ForeignKey("movies.id"), primary_key=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

class RatingModel(Base):
    __tablename__ = "ratings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    movie_id = Column(Integer, ForeignKey("movies.id"), primary_key=True)
    score = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class NotificationModel(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    is_read = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PurchaseModel(Base):
    __tablename__ = "purchases"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    movie_id = Column(Integer, ForeignKey("movies.id"), primary_key=True)
    purchased_at = Column(DateTime(timezone=True), server_default=func.now())
