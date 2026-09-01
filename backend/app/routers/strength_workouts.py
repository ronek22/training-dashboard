from fastapi import APIRouter, Response, status

from ..db import get_db
from ..models.strength_workouts import (
    StrengthActivityLinkRequest,
    StrengthSessionExerciseAddRequest,
    StrengthSessionFinishRequest,
    StrengthSessionPositionRequest,
    StrengthSessionStartRequest,
    StrengthSetCompletionRequest,
    StrengthTemplateInput,
)
from ..services.strength_workouts import (
    abandon_session,
    add_session_exercise,
    activity_candidates,
    complete_set,
    delete_session,
    delete_template,
    exercise_suggestions,
    finish_session,
    get_active_session,
    get_session,
    get_template,
    link_activity,
    list_sessions,
    list_templates,
    save_template,
    set_session_position,
    start_session,
)

router = APIRouter(prefix="/strength/workouts", tags=["strength-workouts"])


def _with_db(callback):
    conn = get_db()
    try:
        return callback(conn)
    finally:
        conn.close()


@router.get("/templates")
def templates_index():
    return _with_db(list_templates)


@router.get("/exercise-suggestions")
def exercise_suggestion_index(q: str = "", limit: int = 12):
    return _with_db(lambda conn: exercise_suggestions(conn, query=q, limit=limit))


@router.post("/templates", status_code=status.HTTP_201_CREATED)
def templates_create(payload: StrengthTemplateInput):
    return _with_db(lambda conn: save_template(conn, payload))


@router.get("/templates/{template_id}")
def templates_show(template_id: int):
    return _with_db(lambda conn: get_template(conn, template_id))


@router.put("/templates/{template_id}")
def templates_update(template_id: int, payload: StrengthTemplateInput):
    return _with_db(lambda conn: save_template(conn, payload, template_id=template_id))


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def templates_delete(template_id: int):
    _with_db(lambda conn: delete_template(conn, template_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sessions")
def sessions_index(limit: int = 20):
    return _with_db(lambda conn: list_sessions(conn, limit=limit))


@router.get("/sessions/active")
def sessions_active():
    return _with_db(get_active_session)


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def sessions_create(payload: StrengthSessionStartRequest):
    return _with_db(lambda conn: start_session(conn, payload.template_id))


@router.get("/sessions/{session_id}")
def sessions_show(session_id: int):
    return _with_db(lambda conn: get_session(conn, session_id))


@router.post("/sessions/{session_id}/exercises", status_code=status.HTTP_201_CREATED)
def sessions_add_exercise(session_id: int, payload: StrengthSessionExerciseAddRequest):
    return _with_db(lambda conn: add_session_exercise(conn, session_id, payload))


@router.post("/sessions/{session_id}/sets/{set_id}/complete")
def sessions_complete_set(session_id: int, set_id: int, payload: StrengthSetCompletionRequest):
    return _with_db(
        lambda conn: complete_set(
            conn,
            session_id,
            set_id,
            payload.actual_reps,
            payload.actual_weight_kg,
        )
    )


@router.post("/sessions/{session_id}/position")
def sessions_position(session_id: int, payload: StrengthSessionPositionRequest):
    return _with_db(
        lambda conn: set_session_position(
            conn,
            session_id,
            payload.exercise_order,
            payload.set_order,
        )
    )


@router.post("/sessions/{session_id}/finish")
def sessions_finish(session_id: int, payload: StrengthSessionFinishRequest):
    return _with_db(lambda conn: finish_session(conn, session_id, payload.linked_activity_id))


@router.post("/sessions/{session_id}/abandon", status_code=status.HTTP_204_NO_CONTENT)
def sessions_abandon(session_id: int):
    _with_db(lambda conn: abandon_session(conn, session_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def sessions_delete(session_id: int):
    _with_db(lambda conn: delete_session(conn, session_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sessions/{session_id}/activity-candidates")
def sessions_activity_candidates(session_id: int):
    return _with_db(lambda conn: activity_candidates(conn, session_id))


@router.put("/sessions/{session_id}/activity")
def sessions_link_activity(session_id: int, payload: StrengthActivityLinkRequest):
    return _with_db(lambda conn: link_activity(conn, session_id, payload.activity_id))
