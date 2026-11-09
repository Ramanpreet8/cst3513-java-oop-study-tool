"""
Course Folder Indexer for CST 3513 Java OOP
Scans course materials recursively, extracts text from .java, .txt, .doc, .docx, and .pdf,
and parses runnable snippets, explanations, and exam questions with solutions.
"""

import os
import re
import json
import subprocess
from typing import Dict, Any, List, Optional, Tuple

class CourseIndexer:
    def __init__(self, course_folder: str):
        self.course_folder = os.path.abspath(course_folder)
        self.files_by_ext: Dict[str, List[str]] = {}
        self.indexed_snippets: List[Dict[str, Any]] = []
        self.indexed_exams: List[Dict[str, Any]] = []
        self.seed_rules: List[Dict[str, Any]] = []
        self.topics = [
            "Decision Structures",
            "Methods & Overloading",
            "Arrays",
            "Classes & Objects",
            "Static Members & References",
            "Inheritance & Super",
            "Overriding & Polymorphism"
        ]

    @staticmethod
    def extract_text_from_file(file_path: str) -> str:
        """Extracts text from .txt, .java, .doc, .docx, and .pdf files."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".txt", ".java", ".html", ".htm", ".json", ".md"):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                return ""

        if ext in (".doc", ".docx", ".rtf"):
            try:
                # Use macOS built-in textutil
                cmd = ["textutil", "-convert", "txt", "-stdout", file_path]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    return res.stdout
            except Exception:
                pass

        if ext == ".pdf":
            try:
                # Extract text using swift PDFKit on macOS
                swift_code = f'''
                import Foundation
                import PDFKit
                let url = URL(fileURLWithPath: "{file_path}")
                if let doc = PDFDocument(url: url) {{
                    for i in 0..<doc.pageCount {{
                        if let s = doc.page(at: i)?.string {{
                            print(s)
                        }}
                    }}
                }}
                '''
                res = subprocess.run(["swift", "-e", swift_code], capture_output=True, text=True, timeout=15)
                if res.returncode == 0:
                    return res.stdout
            except Exception:
                pass

        return ""

    def scan(self) -> Dict[str, Any]:
        """Scans the course folder and indexes all materials."""
        if not os.path.isdir(self.course_folder):
            return {"error": f"Folder not found: {self.course_folder}"}

        all_files = []
        for root, dirs, files in os.walk(self.course_folder):
            for f in files:
                if f.startswith("."):
                    continue
                full_p = os.path.join(root, f)
                ext = os.path.splitext(f)[1].lower()
                self.files_by_ext.setdefault(ext, []).append(full_p)
                all_files.append(full_p)

        # 1. Parse Explanations from "8 Code Explained"
        explanations = self._parse_code_explanations()

        # 2. Parse Code Examples from "4 Code Examples"
        self._parse_code_examples(explanations)

        # 3. Parse Exams & Quizzes from "6 Exams & Quizzes"
        self._parse_exams()

        # 4. Parse Rules & Concepts from "7 Simplified Slides" and Lecture Notes
        self._parse_rules_and_concepts()

        summary = {
            "course_folder": self.course_folder,
            "total_files": len(all_files),
            "files_by_extension": {ext: len(flist) for ext, flist in self.files_by_ext.items()},
            "total_snippets": len(self.indexed_snippets),
            "total_exam_questions": len(self.indexed_exams),
            "total_seed_rules": len(self.seed_rules),
            "topics": self.topics
        }
        return summary

    def _determine_topic(self, filename: str, content: str) -> str:
        """Categorizes snippet or question into one of the 7 core OOP topics."""
        lower_name = filename.lower()
        lower_content = content.lower()

        if "polymorph" in lower_name or "polymorph" in lower_content or "dynamic binding" in lower_content:
            return "Overriding & Polymorphism"
        if "overrid" in lower_name or "override" in lower_content:
            return "Overriding & Polymorphism"
        if "inheritan" in lower_name or "extends" in lower_content or "super" in lower_content:
            return "Inheritance & Super"
        if "static" in lower_name or "static" in lower_content and ("static void" not in lower_content or "static int" in lower_content or "static class" in lower_content):
            return "Static Members & References"
        if "tostring" in lower_name or "clock" in lower_name or "account" in lower_name or "rectangle" in lower_name or "class" in lower_name:
            if "class " in lower_content and ("constructor" in lower_content or "private " in lower_content or "set" in lower_content):
                return "Classes & Objects"
        if "array" in lower_name or "int[]" in lower_content or "string[]" in lower_content:
            return "Arrays"
        if "method" in lower_name or "overload" in lower_name or "max" in lower_name:
            return "Methods & Overloading"
        if "if " in lower_content or "switch" in lower_content or "decision" in lower_name or "while" in lower_content:
            return "Decision Structures"

        return "Classes & Objects"

    def _parse_code_explanations(self) -> Dict[str, Dict[str, str]]:
        """Parses walkthroughs, what it does, concepts, and traps from 8 Code Explained."""
        exps = {}
        for p in self.files_by_ext.get(".docx", []):
            if "8 Code Explained" not in p:
                continue
            base = os.path.basename(p)
            stem = os.path.splitext(base)[0]
            text = self.extract_text_from_file(p)
            if not text:
                continue

            what_it_does = ""
            concept = ""
            walkthrough = ""
            traps = ""

            m_what = re.search(r'What it does\s*[:\n](.*?)(?:Concept it teaches|Walkthrough|$)', text, re.DOTALL)
            if m_what:
                what_it_does = m_what.group(1).strip()

            m_concept = re.search(r'Concept it teaches\s*[:\n](.*?)(?:Walkthrough|Sample output|$)', text, re.DOTALL)
            if m_concept:
                concept = m_concept.group(1).strip()

            m_traps = re.search(r'(?:Exam traps|Key takeaways)\s*[:\n](.*?)$', text, re.DOTALL)
            if m_traps:
                traps = m_traps.group(1).strip()

            exps[stem.lower()] = {
                "what_it_does": what_it_does,
                "concept": concept,
                "traps": traps,
                "full_text": text
            }
        return exps

    def _parse_code_examples(self, explanations: Dict[str, Dict[str, str]]):
        """Extracts individual code snippets from 4 Code Examples."""
        code_files = [f for f in self.files_by_ext.get(".txt", []) if "4 Code Examples" in f]
        snippet_id = 1

        for cpath in sorted(code_files):
            fname = os.path.basename(cpath)
            stem = os.path.splitext(fname)[0]
            raw_text = self.extract_text_from_file(cpath)
            if not raw_text.strip():
                continue

            expl_data = explanations.get(stem.lower(), {})
            topic = self._determine_topic(fname, raw_text)

            # Check if file has sub-snippets like "1.a", "1.b", "1.1", "1.2"
            sub_sections = re.split(r'\n(?=(?:[0-9]+\.[a-zA-Z0-9]+|\/\/\s*Program\s*[0-9]+))', raw_text)
            if len(sub_sections) <= 1:
                sub_sections = [raw_text]

            for idx, sec in enumerate(sub_sections):
                if not ("class " in sec and ("void main" in sec or "static " in sec)):
                    continue

                # Separate code and expected output
                out_match = re.search(r'\n\s*(?:run\s*:|\s*BUILD SUCCESSFUL|Output\s*:)\s*\n?(.*)$', sec, re.DOTALL | re.IGNORECASE)
                expected_output = ""
                clean_code = sec
                if out_match:
                    expected_output = out_match.group(1).strip()
                    clean_code = sec[:out_match.start()].strip()

                # Clean header markers like "1.a." or "1.1" from top of code
                clean_code = re.sub(r'^(?:[0-9]+\.[a-zA-Z0-9]+\.?\s*)+', '', clean_code).strip()

                task_desc = expl_data.get("what_it_does", "")
                if not task_desc:
                    task_desc = f"Implement the Java program from '{fname}' demonstrating {topic}."

                self.indexed_snippets.append({
                    "id": f"snip_{snippet_id}",
                    "file_name": fname,
                    "stem": stem,
                    "sub_id": idx + 1,
                    "title": f"{stem} (Part {idx + 1})" if len(sub_sections) > 1 else stem,
                    "topic": topic,
                    "code": clean_code,
                    "expected_output": expected_output,
                    "what_it_does": task_desc,
                    "concept": expl_data.get("concept", topic),
                    "exam_traps": expl_data.get("traps", "")
                })
                snippet_id += 1

    def _parse_exams(self):
        """Pairs exam papers with solution papers in 6 Exams & Quizzes."""
        exam_files = [f for f in self.files_by_ext.get(".doc", []) + self.files_by_ext.get(".docx", []) if "6 Exams & Quizzes" in f]
        
        # Group by exam family
        pairs = [
            ("CST3513_F26_T1.doc", "CST3513_F26_T1_S.doc", "Test #1"),
            ("R_CST3513_F26_T1.doc", "R_CST3513_F26_T1_S.doc", "Review Test #1"),
            ("CST3513_F26_M.doc", "CST3513_F26_M_S.doc", "Midterm Exam"),
            ("R_CST3513_Midterm_F26.doc", "R_CST3513_Midterm_F26_S.doc", "Review Midterm")
        ]

        qid = 1
        for ep_name, sp_name, exam_title in pairs:
            # Find paths
            ep_path = next((f for f in exam_files if os.path.basename(f) == ep_name), None)
            sp_path = next((f for f in exam_files if os.path.basename(f) == sp_name), None)
            if not ep_path or not sp_path:
                continue

            etxt = self.extract_text_from_file(ep_path)
            stxt = self.extract_text_from_file(sp_path)

            eqs = self._split_numbered_sections(etxt)
            sqs = self._split_numbered_sections(stxt)

            all_nums = sorted(set(list(eqs.keys()) + list(sqs.keys())))
            for num in all_nums:
                q_text = eqs.get(num, "")
                s_text = sqs.get(num, "")
                if not q_text and s_text:
                    q_text = s_text # fallback

                # Extract solution distinct part
                official_solution = s_text
                topic = self._determine_topic(exam_title, q_text)

                self.indexed_exams.append({
                    "id": f"exam_{qid}",
                    "exam_name": exam_title,
                    "question_num": num,
                    "title": f"{exam_title} - Question {num}",
                    "topic": topic,
                    "question_text": q_text.strip(),
                    "official_solution": official_solution.strip()
                })
                qid += 1

    @staticmethod
    def _split_numbered_sections(text: str) -> Dict[int, str]:
        """Splits text by numbered questions (e.g., '1.', '2.')."""
        sections = {}
        pattern = re.compile(r'(?:^|\n)\s*(\d+)\.\s+')
        matches = list(pattern.finditer(text))
        for i, m in enumerate(matches):
            q_num = int(m.group(1))
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections[q_num] = text[start:end].strip()
        return sections

    def _parse_rules_and_concepts(self):
        """Extracts seed rules for cheat sheets and flashcards from Simplified Slides."""
        slide_files = [f for f in self.files_by_ext.get(".docx", []) if "7 Simplified Slides" in f]
        rule_id = 1

        for sp in slide_files:
            fname = os.path.basename(sp)
            text = self.extract_text_from_file(sp)
            if not text:
                continue
            topic = self._determine_topic(fname, text)

            # Split paragraphs or bullet points
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for line in lines:
                # Capture rules, definitions, and formulas
                if len(line) > 25 and (
                    "rule" in line.lower() or "must" in line.lower() or "cannot" in line.lower()
                    or "super" in line.lower() or "overrid" in line.lower() or "private" in line.lower()
                    or "static" in line.lower() or "polymorph" in line.lower() or "constructor" in line.lower()
                ):
                    # Generate a concise front/back rule
                    parts = line.split(":", 1) if ":" in line else line.split(" - ", 1)
                    if len(parts) == 2:
                        front = parts[0].strip()
                        back = parts[1].strip()
                    else:
                        front = f"Rule on {topic}"
                        back = line

                    self.seed_rules.append({
                        "id": f"rule_{rule_id}",
                        "topic": topic,
                        "front": front,
                        "back": back,
                        "source": fname
                    })
                    rule_id += 1
