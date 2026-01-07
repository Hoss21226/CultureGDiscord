import sqlite3
from typing import Optional, List, Tuple
from datetime import datetime

from questions import Question
from question_sets import ALL_QUESTIONS  # <-- on importe toutes les questions


class Database:
    def __init__(self, path: str = "culture.db"):
        self.path = path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_db(self):
        with self._connect() as conn:
            c = conn.cursor()

            # TABLE UTILISATEURS
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

            # TABLE QUESTIONS
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

            # LOGS DE RÉPONSES
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS answer_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id INTEGER NOT NULL,
                    question_id INTEGER,
                    mode TEXT NOT NULL,
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

        # On utilise les questions importées depuis question_sets/*
        cursor.executemany(
            """
            INSERT INTO questions (
                category, difficulty, question,
                choice_a, choice_b, choice_c, choice_d,
                correct_index, explanation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ALL_QUESTIONS,
        )

    # ======================
    # GET RANDOM QUESTION
    # ======================
    def get_random_question(self, category: Optional[str] = None, difficulty: Optional[str] = None) -> Optional[Question]:
        with self._connect() as conn:
            c = conn.cursor()

            query = "SELECT * FROM questions"
            params = []

            conditions = []
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

            return Question(
                id=row[0],
                category=row[1],
                difficulty=row[2],
                question=row[3],
                choices=[row[4], row[5], row[6], row[7]],
                correct_index=row[8],
                explanation=row[9],
            )

    # ======================
    # UPDATE AFTER ANSWER
    # ======================
    def update_after_answer(self, discord_id: int, username: str, correct: bool, question_id: int, mode: str):
        with self._connect() as conn:
            c = conn.cursor()

            # Log
            c.execute(
                """
                INSERT INTO answer_logs (discord_id, question_id, mode, correct, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (discord_id, question_id, mode, int(correct), datetime.utcnow().isoformat()),
            )

            # User exist ?
            c.execute("SELECT id, xp, total_questions, total_correct, streak, best_streak FROM users WHERE discord_id = ?", (discord_id,))
            row = c.fetchone()

            if not row:
                streak = 1 if correct else 0
                best = streak
                c.execute(
                    """
                    INSERT INTO users (discord_id, username, xp, total_questions, total_correct, streak, best_streak)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (discord_id, username, 10 if correct else 0, 1, int(correct), streak, best),
                )
                return

            # Update existing user
            user_id, xp, tq, tc, streak, best = row

            tq += 1
            if correct:
                xp += 10
                tc += 1
                streak += 1
                best = max(best, streak)
            else:
                streak = 0

            c.execute(
                """
                UPDATE users
                SET username = ?, xp = ?, total_questions = ?, total_correct = ?, streak = ?, best_streak = ?
                WHERE discord_id = ?
                """,
                (username, xp, tq, tc, streak, best, discord_id),
            )

    # ======================
    # LEADERBOARD
    # ======================
    def get_leaderboard(self, limit: int = 10):
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT discord_id, username, xp
                FROM users ORDER BY xp DESC LIMIT ?
                """,
                (limit,),
            )
            return c.fetchall()

    def get_profile(self, discord_id: int):
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

            xp, tq, tc, streak, best = row
            accuracy = (tc / tq * 100) if tq > 0 else 0

            return {
                "xp": xp,
                "accuracy": accuracy,
                "total_questions": tq,
                "total_correct": tc,
                "streak": streak,
                "best_streak": best,
            }

    # ======================
    # WEEKLY TOP
    # ======================
    def get_weekly_top(self, limit: int = 5):
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT discord_id, SUM(correct) AS score
                FROM answer_logs
                WHERE created_at >= date('now','-7 days')
                GROUP BY discord_id
                ORDER BY score DESC
                LIMIT ?
                """,
                (limit,),
            )
            return c.fetchall()
db = Database()