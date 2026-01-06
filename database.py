# database.py

import sqlite3
from typing import Optional, List, Tuple
from datetime import datetime

from questions import Question


class Database:
    def __init__(self, path: str = "cultureg.db"):
        self.path = path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_db(self):
        with self._connect() as conn:
            c = conn.cursor()

            # Joueurs
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    xp INTEGER DEFAULT 0,
                    total_questions INTEGER DEFAULT 0,
                    total_correct INTEGER DEFAULT 0,
                    streak INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0
                )
                """
            )

            # Questions
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    question TEXT NOT NULL,
                    choice_a TEXT NOT NULL,
                    choice_b TEXT NOT NULL,
                    choice_c TEXT NOT NULL,
                    choice_d TEXT NOT NULL,
                    correct_index INTEGER NOT NULL,
                    explanation TEXT
                )
                """
            )

            # Logs de réponses (pour les stats quotidiennes / hebdo)
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS answer_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id INTEGER NOT NULL,
                    question_id INTEGER,
                    mode TEXT NOT NULL,         -- 'quiz', 'duel', 'br', 'daily'
                    correct INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            self._seed_questions_if_empty(c)
            conn.commit()

    def _seed_questions_if_empty(self, cursor: sqlite3.Cursor):
        cursor.execute("SELECT COUNT(*) FROM questions")
        (count,) = cursor.fetchone()
        if count > 0:
            return

        questions_data = [
            (
                "Histoire", "facile",
                "En quelle année a débuté la Première Guerre mondiale ?",
                "1912", "1914", "1916", "1918",
                1,
                "Elle commence en 1914 après l'attentat de Sarajevo.",
            ),
            (
                "Géographie", "facile",
                "Quel est le plus grand océan du monde ?",
                "Atlantique", "Arctique", "Pacifique", "Indien",
                2,
                "L'océan Pacifique est le plus vaste.",
            ),
            (
                "Informatique", "moyen",
                "Quel protocole est utilisé pour la navigation web sécurisée ?",
                "HTTP", "FTP", "SSH", "HTTPS",
                3,
                "HTTPS est la version sécurisée de HTTP via TLS/SSL.",
            ),
            (
                "Sport", "facile",
                "Combien de joueurs une équipe de football a-t-elle sur le terrain ?",
                "9", "10", "11", "12",
                2,
                "Une équipe de foot a 11 joueurs sur le terrain.",
            ),
        ]

        cursor.executemany(
            """
            INSERT INTO questions (
                category, difficulty, question,
                choice_a, choice_b, choice_c, choice_d,
                correct_index, explanation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            questions_data,
        )

    # ================= USERS =================

    def ensure_user(self, discord_id: int, username: str):
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR IGNORE INTO users (discord_id, username) VALUES (?, ?)",
                (discord_id, username),
            )
            conn.commit()

    def update_after_answer(
        self,
        discord_id: int,
        username: str,
        correct: bool,
        question_id: Optional[int],
        mode: str,
    ):
        self.ensure_user(discord_id, username)
        now = datetime.utcnow().isoformat()

        with self._connect() as conn:
            c = conn.cursor()

            # log réponse
            c.execute(
                """
                INSERT INTO answer_logs (discord_id, question_id, mode, correct, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (discord_id, question_id, mode, int(correct), now),
            )

            # stats globales
            c.execute(
                """
                SELECT xp, total_questions, total_correct, streak, best_streak
                FROM users WHERE discord_id = ?
                """,
                (discord_id,),
            )
            row = c.fetchone()
            xp, total_q, total_c, streak, best_streak = row

            total_q += 1
            if correct:
                total_c += 1
                xp += 10
                streak += 1
                if streak > best_streak:
                    best_streak = streak
            else:
                streak = 0

            c.execute(
                """
                UPDATE users
                SET xp = ?, total_questions = ?, total_correct = ?,
                    streak = ?, best_streak = ?, username = ?
                WHERE discord_id = ?
                """,
                (xp, total_q, total_c, streak, best_streak, username, discord_id),
            )
            conn.commit()

    def get_profile(self, discord_id: int) -> Optional[dict]:
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT xp, total_questions, total_correct, streak, best_streak
                FROM users WHERE discord_id = ?
                """,
                (discord_id,),
            )
            row = c.fetchone()
            if not row:
                return None
            xp, total_q, total_c, streak, best_streak = row
            accuracy = (total_c / total_q * 100) if total_q > 0 else 0.0
            return {
                "xp": xp,
                "total_questions": total_q,
                "total_correct": total_c,
                "streak": streak,
                "best_streak": best_streak,
                "accuracy": accuracy,
            }

    def get_leaderboard(self, limit: int = 10) -> List[Tuple[int, str, int]]:
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT discord_id, username, xp
                FROM users
                ORDER BY xp DESC
                LIMIT ?
                """,
                (limit,),
            )
            return c.fetchall()

    # ================= QUESTIONS =================

    def get_random_question(
        self,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> Optional[Question]:
        with self._connect() as conn:
            c = conn.cursor()

            query = """
                SELECT id, category, difficulty, question,
                       choice_a, choice_b, choice_c, choice_d,
                       correct_index, explanation
                FROM questions
            """
            conditions = []
            params: List[str] = []

            if category:
                conditions.append("category = ?")
                params.append(category)
            if difficulty:
                conditions.append("difficulty = ?")
                params.append(difficulty)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY RANDOM() LIMIT 1"
            c.execute(query, params)
            row = c.fetchone()
            if not row:
                return None

            (
                qid, category, difficulty, qtext,
                a, b, c_, d,
                idx, explanation,
            ) = row

            return Question(
                id=qid,
                category=category,
                difficulty=difficulty,
                question=qtext,
                choices=[a, b, c_, d],
                correct_index=idx,
                explanation=explanation,
            )

    # ========== REPORTS ==========

    def get_weekly_top(self, limit: int = 5) -> List[Tuple[int, int]]:
        """
        Retourne [(discord_id, bonnes_reponses_sur_la_semaine), ...]
        """
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT discord_id, SUM(correct) as score
                FROM answer_logs
                WHERE created_at >= datetime('now', '-7 days')
                GROUP BY discord_id
                ORDER BY score DESC
                LIMIT ?
                """,
                (limit,),
            )
            return c.fetchall()


db = Database()
