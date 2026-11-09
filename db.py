"""
Database Layer for CST 3513 OOP Study Tool
Handles:
- SQLite persistence of user attempts (type, topic, correct/wrong, date)
- Performance analytics: topic accuracy, current streak, weak spots
- Spaced repetition scheduler (1, 3, 7, 14 days) for flashcards
- Cheat sheet storage with automatic conversion to spaced repetition cards
"""

import sqlite3
import os
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

class Database:
    def __init__(self, db_path: str = "study_tool.db"):
        self.db_path = os.path.abspath(db_path)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self):
        """Initializes tables for attempts, flashcards, cheat sheet, and settings."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Attempts table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exercise_type TEXT NOT NULL,
                topic TEXT NOT NULL,
                item_title TEXT,
                user_answer TEXT,
                expected_answer TEXT,
                is_correct INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Flashcards table (spaced repetition)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                interval_days INTEGER DEFAULT 1,
                repetition_level INTEGER DEFAULT 0,
                next_review_date TEXT NOT NULL,
                last_reviewed_at TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # Cheat Sheet table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cheat_sheet (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                rule_text TEXT NOT NULL,
                source_context TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # Settings table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                val TEXT
            );
            """)
            conn.commit()

    def log_attempt(
        self,
        exercise_type: str,
        topic: str,
        item_title: str,
        user_answer: str,
        expected_answer: str,
        is_correct: bool
    ) -> int:
        """Logs an attempt to SQLite."""
        now_iso = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO attempts (exercise_type, topic, item_title, user_answer, expected_answer, is_correct, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (exercise_type, topic, item_title, user_answer, expected_answer, 1 if is_correct else 0, now_iso))
            conn.commit()
            return cursor.lastrowid

    def add_cheat_sheet_rule(self, topic: str, rule_text: str, source_context: str = "") -> int:
        """Adds a rule to the cheat sheet and automatically seeds it into spaced repetition flashcards."""
        now_iso = datetime.now().isoformat()
        tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO cheat_sheet (topic, rule_text, source_context, created_at)
            VALUES (?, ?, ?, ?)
            """, (topic, rule_text, source_context, now_iso))
            rule_id = cursor.lastrowid

            # Add to flashcards with 1-day interval
            cursor.execute("""
            INSERT INTO flashcards (topic, front, back, interval_days, repetition_level, next_review_date, created_at)
            VALUES (?, ?, ?, 1, 0, ?, ?)
            """, (topic, f"Rule: {topic}", rule_text, tomorrow_str, now_iso))
            conn.commit()
            return rule_id

    def seed_initial_flashcards(self, rules: List[Dict[str, Any]]):
        """Seeds default flashcards if none exist yet."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM flashcards")
            count = cursor.fetchone()[0]
            if count == 0 and rules:
                today_str = date.today().isoformat()
                now_iso = datetime.now().isoformat()
                for r in rules[:30]: # seed first 30 core rules
                    cursor.execute("""
                    INSERT INTO flashcards (topic, front, back, interval_days, repetition_level, next_review_date, created_at)
                    VALUES (?, ?, ?, 1, 0, ?, ?)
                    """, (r.get("topic", "General OOP"), r.get("front", ""), r.get("back", ""), today_str, now_iso))
                conn.commit()

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Calculates accuracy per topic, current streak, due reviews, and weakest topics."""
        today_str = date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total attempts
            cursor.execute("SELECT COUNT(*), SUM(is_correct) FROM attempts")
            row = cursor.fetchone()
            total_attempts = row[0] or 0
            correct_attempts = row[1] or 0
            overall_accuracy = round((correct_attempts / total_attempts) * 100, 1) if total_attempts > 0 else 0.0

            # Streak calculation: count consecutive correct answers ending at most recent attempt
            cursor.execute("SELECT is_correct FROM attempts ORDER BY id DESC")
            attempts_rev = cursor.fetchall()
            current_streak = 0
            for att in attempts_rev:
                if att["is_correct"] == 1:
                    current_streak += 1
                else:
                    break

            # Due flashcards today
            cursor.execute("SELECT COUNT(*) FROM flashcards WHERE next_review_date <= ?", (today_str,))
            due_flashcards = cursor.fetchone()[0] or 0

            # Accuracy per topic
            cursor.execute("""
            SELECT 
                topic, 
                COUNT(*) as total, 
                SUM(is_correct) as correct
            FROM attempts
            GROUP BY topic
            """)
            topic_stats = []
            topic_rows = cursor.fetchall()
            for tr in topic_rows:
                tot = tr["total"]
                corr = tr["correct"] or 0
                acc = round((corr / tot) * 100, 1)
                topic_stats.append({
                    "topic": tr["topic"],
                    "total": tot,
                    "correct": corr,
                    "wrong": tot - corr,
                    "accuracy": acc
                })

            # Sort topics by accuracy ascending (weakest first)
            weak_topics = sorted(topic_stats, key=lambda x: (x["accuracy"], -x["wrong"]))

            # Cheat sheet count
            cursor.execute("SELECT COUNT(*) FROM cheat_sheet")
            cheat_sheet_count = cursor.fetchone()[0] or 0

            return {
                "total_attempts": total_attempts,
                "correct_attempts": correct_attempts,
                "overall_accuracy": overall_accuracy,
                "current_streak": current_streak,
                "due_flashcards": due_flashcards,
                "topic_stats": topic_stats,
                "weak_topics": [t["topic"] for t in weak_topics],
                "cheat_sheet_count": cheat_sheet_count
            }

    def get_due_flashcards(self) -> List[Dict[str, Any]]:
        """Returns flashcards due for review today or overdue."""
        today_str = date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM flashcards 
            WHERE next_review_date <= ? 
            ORDER BY next_review_date ASC, id ASC
            """, (today_str,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def review_flashcard(self, card_id: int, got_it: bool) -> Dict[str, Any]:
        """
        Advances or resets spaced repetition intervals:
        Intervals: 1 -> 3 -> 7 -> 14 days.
        """
        intervals = [1, 3, 7, 14]
        today = date.today()
        now_iso = datetime.now().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT repetition_level, topic, front FROM flashcards WHERE id = ?", (card_id,))
            row = cursor.fetchone()
            if not row:
                return {"error": "Card not found"}

            curr_level = row["repetition_level"]
            topic = row["topic"]

            if got_it:
                next_level = min(curr_level + 1, len(intervals) - 1)
                interval_days = intervals[next_level]
            else:
                next_level = 0
                interval_days = 1

            next_review = (today + timedelta(days=interval_days)).isoformat()

            cursor.execute("""
            UPDATE flashcards 
            SET repetition_level = ?, interval_days = ?, next_review_date = ?, last_reviewed_at = ?
            WHERE id = ?
            """, (next_level, interval_days, next_review, now_iso, card_id))

            # Log attempt
            cursor.execute("""
            INSERT INTO attempts (exercise_type, topic, item_title, user_answer, expected_answer, is_correct, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("flashcard", topic, f"Flashcard #{card_id}: {row['front'][:30]}", "Got it" if got_it else "Missed", "Got it", 1 if got_it else 0, now_iso))

            conn.commit()
            return {
                "card_id": card_id,
                "got_it": got_it,
                "interval_days": interval_days,
                "next_review_date": next_review
            }

    def get_cheat_sheet_rules(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all rules saved to cheat sheet."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if topic:
                cursor.execute("SELECT * FROM cheat_sheet WHERE topic = ? ORDER BY id DESC", (topic,))
            else:
                cursor.execute("SELECT * FROM cheat_sheet ORDER BY id DESC")
            return [dict(r) for r in cursor.fetchall()]

    def get_setting(self, key: str, default: str = "") -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT val FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["val"] if row else default

    def set_setting(self, key: str, val: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, val))
            conn.commit()
