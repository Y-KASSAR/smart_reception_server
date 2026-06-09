

from typing import List, Optional
from sqlalchemy.orm import Session
from database.models import FaceEmbedding
from utils.crypto_utils import encrypt_embedding


class FaceEmbeddingRepository:

    @staticmethod
    def get_by_guest(db: Session, guest_id: int) -> List[FaceEmbedding]:
        return db.query(FaceEmbedding).filter(FaceEmbedding.guest_id == guest_id).all()
    
    @staticmethod
    def get_by_id(db: Session, embedding_id: int) -> Optional[FaceEmbedding]: 
        return db.query(FaceEmbedding).filter(FaceEmbedding.id == embedding_id).first()
    

    @staticmethod
    def create(
        db: Session,
        guest_id: int,
        embedding_bytes: bytes,
        source: str = "enrollment",
        quality_score: Optional[float] = None,
    ) -> FaceEmbedding:
        encrypted = encrypt_embedding(embedding_bytes)
        emb = FaceEmbedding(
            guest_id=guest_id,
            embedding_vector=encrypted,
            source =source,
            quality_score=quality_score,
        )      
        db.add(emb)
        db.commit()
        db.refresh(emb)
        return emb
    
    @staticmethod
    def delete(db: Session, embedding_id: int) -> bool:
        emb = db.query(FaceEmbedding).filter(FaceEmbedding.id == embedding_id).first()
        if not emb:
            return False
        try:  # adjusted
            db.delete(emb)
            db.commit()
            return True
        except Exception:
            db.rollback()  # adjusted
            raise
    
    @staticmethod
    def delete_by_guest(db: Session, guest_id: int)-> bool:
        try:  # adjusted
            count = (
                db.query(FaceEmbedding)
                .filter(FaceEmbedding.guest_id == guest_id)
                .delete()
            )
            db.commit()
            return count > 0  # adjusted
        except Exception:
            db.rollback()  # adjusted
            raise  # adjusted
    
    @staticmethod
    def count_for_guest(db: Session, guest_id: int) ->int:
        return db.query(FaceEmbedding).filter(FaceEmbedding.guest_id == guest_id).count()

     