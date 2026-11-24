import os
from contextlib import contextmanager
import mysql.connector


@contextmanager
def database():
    conn = mysql.connector.connect(host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")), user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"], database=os.getenv("MYSQL_DATABASE", "stock_tracker"),
        charset="utf8mb4", time_zone="+00:00")
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
