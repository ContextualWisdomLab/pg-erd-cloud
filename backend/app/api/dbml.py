from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.ddl.export import snapshot_json_to_sql
from app.schemas import DbmlConvertIn, DbmlConvertOut
from app.spec.dbml_import import parse_dbml

router = APIRouter(prefix="/api/dbml", tags=["dbml"])


@router.post("/convert", response_model=DbmlConvertOut)
async def convert_dbml(
    body: DbmlConvertIn,
    user: CurrentUser = Depends(get_current_user),
) -> DbmlConvertOut:
    """Design-first entry point: DBML text → snapshot JSON (+ optional DDL).

    The returned snapshot has the same shape introspection produces, so the
    whole downstream pipeline (ERD, DDL export, diff, migration, analyzers)
    works on a design that never touched a database. Pure computation — no
    project resources involved, so authentication alone suffices.
    """
    snapshot = parse_dbml(body.dbml)
    ddl = (
        snapshot_json_to_sql(snapshot, target_dialect=body.dialect)
        if body.include_ddl
        else None
    )
    return DbmlConvertOut(
        snapshot_json=snapshot,
        ddl=ddl,
        tables=len(snapshot["relations"]),
        foreign_keys=len(snapshot["fk_edges"]),
    )
