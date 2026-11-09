#!/usr/bin/env python3
"""
CST 3513 Java OOP Study Tool - Main Web Server
Runs locally on Flask (or zero-dependency built-in HTTP server fallback).
Serves all 6 study modes, SQLite tracking, JDK detection, and course indexing.
"""

import os
import sys
import json
import random
import argparse
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Local modules
from java_runner import JavaRunner
from indexer import CourseIndexer
from db import Database

# Global singletons
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
DEFAULT_COURSE_DIR = os.path.join(BASE_DIR, "course_materials", "CST 3513 Java OOP")

runner = JavaRunner()
db = Database(os.path.join(BASE_DIR, "study_tool.db"))
indexer = None
index_summary = {}

def init_app(course_dir: str = None):
    global indexer, index_summary
    target_dir = course_dir or db.get_setting("course_folder", DEFAULT_COURSE_DIR)
    print("=" * 65)
    print("🎓 CST 3513 Java OOP Local Study Tool")
    print("=" * 65)

    # 1. Check JDK on startup
    print(f"\n[1/3] Checking Java Development Kit (JDK)...")
    if runner.is_ready:
        print(f"  ✅ JDK detected: {runner.jdk_info.get('version')} at {runner.jdk_info.get('location')}")
    else:
        print(f"  ❌ JDK NOT FOUND!")
        print(runner.jdk_info.get("fix_instructions", "Install openjdk or configure JAVA_HOME."))

    # 2. Index course folder
    print(f"\n[2/3] Indexing course materials from:\n  📁 {target_dir}")
    indexer = CourseIndexer(target_dir)
    index_summary = indexer.scan()
    if "error" in index_summary:
        print(f"  ⚠️ Warning: {index_summary['error']}")
    else:
        print(f"  ✅ Indexed {index_summary.get('total_files', 0)} files:")
        for ext, count in index_summary.get("files_by_extension", {}).items():
            print(f"     - {count} {ext} files")
        print(f"  ✅ Prepared {index_summary.get('total_snippets', 0)} runnable code snippets")
        print(f"  ✅ Prepared {index_summary.get('total_exam_questions', 0)} exam questions with official keys")
        print(f"  ✅ Extracted {index_summary.get('total_seed_rules', 0)} core OOP rules")

    # 3. Seed initial flashcards
    print(f"\n[3/3] Checking database & spaced repetition deck...")
    if indexer.seed_rules:
        db.seed_initial_flashcards(indexer.seed_rules)
    stats = db.get_dashboard_stats()
    print(f"  ✅ Loaded attempts: {stats['total_attempts']}, current streak: {stats['current_streak']}, due cards: {stats['due_flashcards']}")
    print("=" * 65)

# API Handlers
def handle_api_status():
    stats = db.get_dashboard_stats()
    return {
        "jdk": runner.jdk_info,
        "stats": stats,
        "topics": indexer.topics if indexer else [],
        "index_summary": index_summary
    }

def handle_api_dashboard():
    stats = db.get_dashboard_stats()
    return {
        "stats": stats,
        "index_summary": index_summary
    }

def handle_api_rescan(payload):
    global indexer, index_summary
    path = payload.get("path", "").strip()
    if not os.path.isdir(path):
        return {"error": f"Directory not found: {path}"}
    db.set_setting("course_folder", path)
    indexer = CourseIndexer(path)
    index_summary = indexer.scan()
    return index_summary

def handle_api_snippets_random(params):
    topic = params.get("topic", [None])[0]
    candidates = indexer.indexed_snippets if indexer else []
    if topic:
        candidates = [s for s in candidates if s["topic"] == topic]
    if not candidates:
        return {"error": f"No code snippets found for topic: {topic}" if topic else "No snippets indexed."}
    snip = random.choice(candidates)
    return {
        "id": snip["id"],
        "title": snip["title"],
        "topic": snip["topic"],
        "code": snip["code"],
        "file_name": snip["file_name"],
        "what_it_does": snip["what_it_does"]
    }

def handle_api_predict_run(payload):
    snip_id = payload.get("snippet_id")
    user_pred = payload.get("prediction", "").strip()

    snip = next((s for s in indexer.indexed_snippets if s["id"] == snip_id), None)
    if not snip:
        return {"error": "Snippet not found"}

    # Run real compilation and execution
    exec_res = runner.compile_and_run(snip["code"])
    actual_out = exec_res.get("output", "").strip()

    # Normalize outputs for diffing (whitespace-insensitive line matching)
    norm_user = "\n".join(line.strip() for line in user_pred.splitlines() if line.strip())
    norm_actual = "\n".join(line.strip() for line in actual_out.splitlines() if line.strip())
    is_match = (norm_user == norm_actual) and bool(norm_actual)

    # Log attempt
    db.log_attempt(
        exercise_type="predict_output",
        topic=snip["topic"],
        item_title=snip["title"],
        user_answer=user_pred,
        expected_answer=actual_out,
        is_correct=is_match
    )

    return {
        "matched": is_match,
        "actual_output": actual_out,
        "compiled": exec_res.get("compiled", False),
        "error": exec_res.get("error", "")
    }

def handle_api_compile_snippet():
    candidates = indexer.indexed_snippets if indexer else []
    if not candidates:
        return {"error": "No snippets available"}
    snip = random.choice(candidates)
    mut_code, has_bug, btype, explanation = runner.inject_bug(snip["code"])
    return {
        "title": snip["title"],
        "topic": snip["topic"],
        "code": mut_code,
        "has_bug": has_bug,
        "bug_type": btype,
        "bug_explanation": explanation
    }

def handle_api_compile_verify(payload):
    code = payload.get("code", "")
    topic = payload.get("topic", "General OOP")
    title = payload.get("title", "Snippet")
    has_bug = payload.get("has_injected_bug", False)
    bug_explanation = payload.get("bug_explanation", "")
    user_guess_compiles = payload.get("user_guess_compiles", True)
    user_detail = payload.get("user_detail", "")

    # Truly compile with real javac!
    c_res = runner.compile_and_run(code)
    really_compiled = c_res.get("compiled", False) and c_res.get("exit_code", -1) == 0

    user_correct = (user_guess_compiles == really_compiled)

    db.log_attempt(
        exercise_type="does_it_compile",
        topic=topic,
        item_title=title,
        user_answer=f"Compiles: {user_guess_compiles} ({user_detail})",
        expected_answer=f"Compiles: {really_compiled} - {bug_explanation}",
        is_correct=user_correct
    )

    return {
        "is_correct": user_correct,
        "really_compiled": really_compiled,
        "compiler_message": c_res.get("error", ""),
        "runtime_output": c_res.get("output", ""),
        "explanation": bug_explanation if not really_compiled else "The code compiles and executes without errors."
    }

def handle_api_memory_random(params):
    topic = params.get("topic", [None])[0]
    candidates = indexer.indexed_snippets if indexer else []
    if topic:
        candidates = [s for s in candidates if s["topic"] == topic]
    if not candidates:
        return {"error": "No snippet available"}
    snip = random.choice(candidates)
    return {
        "id": snip["id"],
        "title": snip["title"],
        "topic": snip["topic"],
        "what_it_does": snip["what_it_does"],
        "concept": snip["concept"],
        "code": snip["code"]
    }

def handle_api_memory_test(payload):
    code = payload.get("code", "")
    topic = payload.get("topic", "General OOP")
    title = payload.get("title", "Memory Task")

    c_res = runner.compile_and_run(code)
    return {
        "compiled": c_res.get("compiled", False) and c_res.get("exit_code", -1) == 0,
        "output": c_res.get("output", ""),
        "error": c_res.get("error", "")
    }

def handle_api_exams_random(params):
    exam_name = params.get("exam_name", [None])[0]
    candidates = indexer.indexed_exams if indexer else []
    if exam_name:
        candidates = [e for e in candidates if e["exam_name"] == exam_name]
    if not candidates:
        return {"error": "No exam questions indexed"}
    q = random.choice(candidates)
    all_exams = sorted(list(set(e["exam_name"] for e in indexer.indexed_exams)))
    return {
        "id": q["id"],
        "title": q["title"],
        "exam_name": q["exam_name"],
        "topic": q["topic"],
        "question_text": q["question_text"],
        "all_exams": all_exams
        # Note: official_solution is strictly kept on the server until submitted!
    }

def handle_api_exams_reveal(payload):
    qid = payload.get("question_id")
    user_answer = payload.get("user_answer", "").strip()

    q = next((e for e in indexer.indexed_exams if e["id"] == qid), None)
    if not q:
        return {"error": "Question not found"}

    return {
        "official_solution": q["official_solution"]
    }

def handle_api_log_attempt(payload):
    db.log_attempt(
        exercise_type=payload.get("exercise_type", "practice"),
        topic=payload.get("topic", "General OOP"),
        item_title=payload.get("item_title", ""),
        user_answer=payload.get("user_answer", "User submission"),
        expected_answer=payload.get("expected_answer", ""),
        is_correct=bool(payload.get("is_correct", False))
    )
    return {"status": "ok"}

def handle_api_flashcards_due():
    cards = db.get_due_flashcards()
    return {"cards": cards}

def handle_api_flashcards_review(payload):
    card_id = payload.get("card_id")
    got_it = bool(payload.get("got_it", False))
    res = db.review_flashcard(card_id, got_it)
    return res

def handle_api_cheat_sheet():
    rules = db.get_cheat_sheet_rules()
    return {"rules": rules}

def handle_api_cheat_sheet_add(payload):
    topic = payload.get("topic", "General OOP")
    rule_text = payload.get("rule_text", "").strip()
    source = payload.get("source_context", "")
    rule_id = db.add_cheat_sheet_rule(topic, rule_text, source)
    return {"status": "ok", "rule_id": rule_id}

def handle_api_weak_spot():
    stats = db.get_dashboard_stats()
    weak_topics = stats.get("weak_topics", [])
    target_topic = weak_topics[0] if weak_topics else "Inheritance & Super"

    # Find topic accuracy
    t_stat = next((ts for ts in stats.get("topic_stats", []) if ts["topic"] == target_topic), None)
    acc = t_stat["accuracy"] if t_stat else 0

    # Pick an exercise for this weak topic
    matching_snips = [s for s in indexer.indexed_snippets if s["topic"] == target_topic]
    matching_exams = [e for e in indexer.indexed_exams if e["topic"] == target_topic]

    exercise = None
    if matching_snips and random.random() < 0.6:
        snip = random.choice(matching_snips)
        ex_type = random.choice(["predict_output", "does_it_compile", "write_from_memory"])
        labels = {
            "predict_output": "Predict Output",
            "does_it_compile": "Does It Compile?",
            "write_from_memory": "Write From Memory"
        }
        exercise = {
            "type": ex_type,
            "type_label": labels[ex_type],
            "title": snip["title"],
            "code": snip["code"]
        }
    elif matching_exams:
        q = random.choice(matching_exams)
        exercise = {
            "type": "exam_style",
            "type_label": "Exam Practice",
            "title": q["title"],
            "question_text": q["question_text"]
        }
    elif matching_snips:
        snip = random.choice(matching_snips)
        exercise = {
            "type": "predict_output",
            "type_label": "Predict Output",
            "title": snip["title"],
            "code": snip["code"]
        }

    return {
        "target_topic": target_topic,
        "topic_accuracy": acc,
        "exercise": exercise
    }

# HTTP Request Handler (Standard Library)
class StudyToolHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(os.path.join(TEMPLATES_DIR, "index.html"), "rb") as f:
                self.wfile.write(f.read())
            return

        api_routes = {
            "/api/status": handle_api_status,
            "/api/dashboard": handle_api_dashboard,
            "/api/snippets/random": lambda: handle_api_snippets_random(params),
            "/api/compile_check/snippet": handle_api_compile_snippet,
            "/api/memory/random": lambda: handle_api_memory_random(params),
            "/api/exams/random": lambda: handle_api_exams_random(params),
            "/api/flashcards/due": handle_api_flashcards_due,
            "/api/cheat_sheet": handle_api_cheat_sheet,
            "/api/weak_spot": handle_api_weak_spot
        }

        if path in api_routes:
            res_data = api_routes[path]()
            self._send_json(res_data)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        api_routes = {
            "/api/rescan": lambda: handle_api_rescan(payload),
            "/api/predict/run": lambda: handle_api_predict_run(payload),
            "/api/compile_check/verify": lambda: handle_api_compile_verify(payload),
            "/api/memory/test": lambda: handle_api_memory_test(payload),
            "/api/exams/reveal": lambda: handle_api_exams_reveal(payload),
            "/api/log_attempt": lambda: handle_api_log_attempt(payload),
            "/api/flashcards/review": lambda: handle_api_flashcards_review(payload),
            "/api/cheat_sheet/add": lambda: handle_api_cheat_sheet_add(payload)
        }

        if path in api_routes:
            res_data = api_routes[path]()
            self._send_json(res_data)
        else:
            self.send_error(404, "Not Found")

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        # Concise logging
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def main():
    parser = argparse.ArgumentParser(description="CST 3513 Java OOP Study Tool")
    parser.add_argument("--course-dir", type=str, default=DEFAULT_COURSE_DIR, help="Path to course materials")
    parser.add_argument("--port", type=int, default=5050, help="Port to run the server on (default 5050)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface")
    args = parser.parse_args()

    init_app(args.course_dir)

    server = ThreadedHTTPServer((args.host, args.port), StudyToolHTTPHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"\n🚀 Study Tool Web Server running at:")
    print(f"   👉 {url}\n")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()

if __name__ == "__main__":
    main()
