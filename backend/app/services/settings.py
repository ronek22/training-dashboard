from ..db import get_db
from ..repositories.settings import get_setting_value, set_setting_value


def get_setting(key: str):
    conn = get_db()
    try:
        return get_setting_value(conn, key)
    finally:
        conn.close()


def set_setting(key: str, value: str):
    conn = get_db()
    try:
        set_setting_value(conn, key, value)
        conn.commit()
    finally:
        conn.close()
