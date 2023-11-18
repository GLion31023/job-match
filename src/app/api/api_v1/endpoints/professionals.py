from typing import Annotated, List
from fastapi import Depends, APIRouter
from app.core.auth import get_current_user
from app.crud.crud_user import create_user
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import DbProfessionals
from app.schemas.professional import ProfessionalCreate, ProfessionalCreateDisplay, ProfessionalDisplay
from app.schemas.user import UserDisplay


router = APIRouter()


@router.post('/professionals', response_model=ProfessionalCreateDisplay)
async def create_professional(request: ProfessionalCreate, db: Annotated[Session, Depends(get_db)]):
    return await create_user(db, request)


@router.get('/professionals', response_model=List[ProfessionalDisplay])
def get_professionals(db: Annotated[Session, Depends(get_db)],
                      current_user: Annotated[UserDisplay, Depends(get_current_user)]):
    professionals = db.query(DbProfessionals).all()
    return professionals
