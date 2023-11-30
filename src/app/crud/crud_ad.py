from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from typing import Type, List, Optional, Union, TypeVar

from app.db.models import DbUsers, DbProfessionals, DbCompanies, DbAds, DbSkills, adds_skills, DbInfo, DbJobsMatches
from app.schemas.ad import AdCreate, AdSkills, AddSkillToAdDisplay, AdDisplay, ResumeStatus, JobAdStatus, SkillLevel

AdModelType = TypeVar('AdModelType', bound=Union[Type[DbAds], DbAds])
SkillModelType = TypeVar('SkillModelType', bound=Union[Type[DbSkills], DbSkills])
CompanyModelType = TypeVar('CompanyModelType', bound=Union[Type[DbCompanies], DbCompanies])
ProfessionalModelType = TypeVar('ProfessionalModelType', bound=Union[Type[DbProfessionals], DbProfessionals])


async def create_ad_crud(db: Session, current_user: DbUsers, schema: AdCreate) -> DbAds:
    professional = await get_professional(db, current_user)
    company = await get_company(db, current_user)
    user_info = await professional.info_id if professional else company.info_id if company else None

    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Complete your info before creating an ad')

    is_resume = current_user.type == 'professional'
    new_ad = DbAds(
        description=schema.description,
        location=schema.location,
        status=schema.status.value,
        min_salary=schema.min_salary,
        max_salary=schema.max_salary,
        info_id=user_info,
        is_resume=is_resume)

    db.add(new_ad)
    db.commit()

    return new_ad


async def get_resumes_crud(db: Session, description: Optional[str] = None, location: Optional[str] = None,
                           ad_status: Optional[ResumeStatus] = None, min_salary: Optional[int] = None,
                           max_salary: Optional[int] = None, page: Optional[int] = 1) -> List[Type[AdDisplay]]:

    query = db.query(DbAds).filter(DbAds.is_resume == True, DbAds.is_deleted == False)
    query = await filter_ads(query, description, location, ad_status, min_salary, max_salary)
    ads = await paginate(query, page)

    if not ads:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="There are no results for your search")

    return ads


async def get_job_ads_crud(db: Session, description: Optional[str] = None, location: Optional[str] = None,
                           ad_status: Optional[JobAdStatus] = None, min_salary: Optional[int] = None,
                           max_salary: Optional[int] = None, page: Optional[int] = 1) -> List[Type[AdDisplay]]:

    query = db.query(DbAds).filter(DbAds.is_resume == False, DbAds.is_deleted == False)
    query = await filter_ads(query, description, location, ad_status, min_salary, max_salary)
    ads = await paginate(query, page)

    if not ads:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="There are no results for your search")

    return ads


async def update_resumes_crud(db: Session, current_user: DbUsers, ad_id: str,
                              description: Optional[str] = None, location: Optional[str] = None,
                              ad_status: Optional[ResumeStatus] = None, min_salary: Optional[int] = None,
                              max_salary: Optional[int] = None) -> AdModelType:

    ad = await get_ad(db, ad_id)
    if not ad.is_resume:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot update job ads')

    professional = await get_professional(db, current_user)
    await check_user_authorization(current_user, professional, ad)
    await update_ad(ad, description, location, ad_status, min_salary, max_salary)

    db.commit()

    return ad


async def update_job_ads_crud(db: Session, current_user: DbUsers, ad_id: str,
                              description: Optional[str] = None, location: Optional[str] = None,
                              ad_status: Optional[JobAdStatus] = None, min_salary: Optional[int] = None,
                              max_salary: Optional[int] = None) -> AdModelType:

    ad = await get_ad(db, ad_id)
    if ad.is_resume:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot update resumes')

    company = await get_company(db, current_user)
    await check_user_authorization(current_user, company, ad)
    await update_ad(ad, description, location, ad_status, min_salary, max_salary)

    db.commit()

    return ad


async def get_ad_by_id_crud(db: Session, ad_id: str) -> Type[AdDisplay]:
    ad = await get_ad(db, ad_id)
    return ad


async def delete_ad_crud(db: Session, ad_id: str, current_user: DbUsers) -> None:
    ad = await get_ad(db, ad_id)
    professional = await get_professional(db, current_user)
    company = await get_company(db, current_user)

    if professional:
        await check_user_authorization(current_user, professional, ad)
        await if_main_resume(db, ad)
    else:
        await check_user_authorization(current_user, company, ad)

    await delete_job_matches(db, ad)
    ad.is_deleted = True

    db.commit()

    return


async def create_new_skill(db: Session, schema: AdSkills) -> DbSkills:
    await new_skill_already_exists(db, schema.name)
    new_skill = DbSkills(name=schema.name)
    db.add(new_skill)

    db.commit()
    db.refresh(new_skill)

    return new_skill


async def get_skills_crud(db: Session, page: Optional[int] = 1) -> List[Type[AdSkills]]:
    query = db.query(DbSkills).filter(DbSkills.is_deleted == False)
    skills = await paginate(query, page, 5)

    if not skills:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail='There are no available skills to display, add a skill first')

    return skills


async def update_skill_crud(db: Session, skill_name: str, new_name: str) -> SkillModelType:
    skill = await get_skill(db, skill_name)
    await new_skill_already_exists(db, new_name)
    skill.name = new_name

    db.commit()
    db.refresh(skill)

    return skill


async def delete_skill_crud(db: Session, skill_name: str) -> None:
    skill = await get_skill(db, skill_name)
    skill.is_deleted = True

    db.commit()

    return


async def add_skill_to_ad_crud(db: Session, ad_id: str, skill_name: str, level: SkillLevel) -> AddSkillToAdDisplay:
    ad = await get_ad(db, ad_id)
    skill = await get_skill(db, skill_name)

    skill_already_added = db.query(adds_skills) \
        .join(DbSkills, adds_skills.c.skill_id == str(skill.id)) \
        .join(DbAds, adds_skills.c.ad_id == str(ad.id)) \
        .filter(DbAds.id == ad_id, DbSkills.name == skill_name) \
        .first()

    if skill_already_added:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{skill_name}' already added to this ad")

    ad_skill = adds_skills.insert().values(ad_id=ad.id, skill_id=skill.id, level=level.value)

    db.execute(ad_skill)
    db.commit()

    return AddSkillToAdDisplay(
        skill_name=skill.name,
        level=level)


async def remove_skill_from_ad_crud(db: Session, ad_id: str, skill_name: str) -> None:
    ad = await get_ad(db, ad_id)
    skill = await get_skill(db, skill_name)

    skill_to_remove = (db.query(adds_skills)
                       .join(DbSkills, adds_skills.c.skill_id == str(skill.id))
                       .join(DbAds, adds_skills.c.ad_id == str(ad.id))
                       .filter(DbAds.id == ad_id, DbSkills.name == skill_name)
                       .first())

    if not skill_to_remove:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"'{skill_name}' does not exist in this ad")

    db.execute(
        adds_skills.delete().where(
            adds_skills.c.ad_id == ad_id,
            adds_skills.c.skill_id == skill.id))

    db.commit()

    return


async def filter_ads(query, description=None, location=None, ad_status=None, min_salary=None, max_salary=None):
    if description:
        keywords = description.split()
        for keyword in keywords:
            query = query.filter(DbAds.description.ilike(f'%{keyword}%'))
    if location:
        query = query.filter(DbAds.location.ilike(f'%{location}%'))
    if ad_status:
        query = query.filter(DbAds.status == ad_status.value)
    if min_salary:
        query = query.filter(DbAds.min_salary >= min_salary)
    if max_salary:
        query = query.filter(DbAds.max_salary <= max_salary)

    return query


async def update_ad(ad: Type[DbAds], description: Optional[str] = None, location: Optional[str] = None,
                    ad_status: Union[Optional[JobAdStatus], Optional[ResumeStatus], None] = None,
                    min_salary: Optional[int] = None, max_salary: Optional[int] = None):
    if description is not None:
        ad.description = description
    if location is not None:
        ad.location = location
    if ad_status is not None:
        ad.status = ad_status.value
    if min_salary is not None:
        ad.min_salary = min_salary
    if max_salary is not None:
        ad.max_salary = max_salary


async def paginate(query, page: int, page_size: Optional[int] = 3):
    return query.limit(page_size).offset((page - 1) * page_size).all()


async def get_ad(db: Session, ad_id: str) -> AdModelType:
    ad = db.query(DbAds).filter(DbAds.id == ad_id, DbAds.is_deleted == False).first()
    if not ad:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Ad not found')

    return ad


async def get_skill(db: Session, skill_name: str) -> SkillModelType:
    skill = db.query(DbSkills).filter(DbSkills.name == skill_name, DbSkills.is_deleted == False).first()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Skill not found')

    return skill


async def new_skill_already_exists(db: Session, skill_name: str) -> None:
    skill = db.query(DbSkills).filter(DbSkills.name == skill_name, DbSkills.is_deleted == False).first()
    if skill:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Skill with name '{skill_name}' already"
                                                                            f" exists")


async def get_professional(db: Session, current_user: DbUsers) -> ProfessionalModelType | None:
    professional = db.query(DbProfessionals).filter(DbProfessionals.user_id == str(current_user.id)).first()

    return professional


async def get_company(db: Session, current_user: DbUsers) -> CompanyModelType | None:
    company = db.query(DbCompanies).filter(DbCompanies.user_id == str(current_user.id)).first()

    return company


async def check_user_authorization(user: DbUsers, author: Union[ProfessionalModelType, CompanyModelType],
                                   ad: AdModelType):
    if user.type != 'admin' and author.info_id != ad.info_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only the author can apply changes')


async def if_main_resume(db: Session, ad: AdModelType) -> None:
    resume = db.query(DbInfo).filter(DbInfo.main_ad == str(ad.id)).first()
    if resume:
        resume.main_ad = None
        return


async def delete_job_matches(db: Session, ad: AdModelType):
    if ad.is_resume:
        job_matches = db.query(DbJobsMatches).filter(DbJobsMatches.resume_id == str(ad.id)).all()
    else:
        job_matches = db.query(DbJobsMatches).filter(DbJobsMatches.ad_id == str(ad.id)).all()

    for j_m in job_matches:
        j_m.is_deleted = True

    return
