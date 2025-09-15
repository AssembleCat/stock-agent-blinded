import sqlite3
from typing import Any, List, Tuple, Optional

DB_PATH = "market.db"


class SqliteDBClient:
    """
    SQLite 데이터베이스 인스턴스 기반 클라이언트
    사용 예시:
        db = SqliteDBClient()
        results = db.execute("SELECT * FROM ...", params)
        db.close()
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def execute(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        cursor = self.conn.execute(query, params)
        return cursor.fetchall()

    def execute_with_columns(
        self, query: str, params: tuple = ()
    ) -> Tuple[List[str], List[sqlite3.Row]]:
        cursor = self.conn.execute(query, params)
        columns = [description[0] for description in cursor.description]
        results = cursor.fetchall()
        return columns, results

    def fetch_query(self, query: str, params: tuple = ()) -> Tuple[List[sqlite3.Row], List[str]]:
        """
        쿼리를 실행하고 결과와 컬럼명을 반환합니다.
        기존 코드와의 호환성을 위해 추가된 메서드입니다.
        """
        cursor = self.conn.execute(query, params)
        columns = [description[0] for description in cursor.description]
        results = cursor.fetchall()
        return results, columns

    def close(self):
        self.conn.close()
