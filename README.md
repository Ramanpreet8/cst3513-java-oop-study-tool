# CST 3513 Java OOP Local Study Tool

A dedicated, local exam-prep tool built for **CST 3513 (Object-Oriented Programming with Java)**. It runs entirely on your local machine with Python, uses SQLite for attempt tracking and spaced repetition, and performs real-time Java compilation and execution using your local JDK.

---

## Quick Start

### 1. Launch the Application
From the project folder:
```bash
./run.sh
```
Or directly with Python:
```bash
python3 app.py
```

By default, the server runs at:
👉 **[http://127.0.0.1:5050](http://127.0.0.1:5050)**

Open this URL in your web browser.

---

## Real Course Materials Structure Found

The tool inspected and indexed the uploaded CST 3513 course directory (`168 files total`):
- `1 Syllabus & Course Info`: Syllabus docx and syllabus table of contents HTML files.
- `2 Lecture Notes`: 19 docx files + 1 PDF (`Inheritance_Access_Modifier.pdf`).
- `3 Slides`: 19 slide presentations (`.ppt` / `.pptx`).
- `4 Code Examples`: 48 source files containing 107 runnable code examples with output traces.
- `5 Homework & Classwork`: 6 docx problem statements and homework assignments.
- `6 Exams & Quizzes`: 8 paired exam papers and official solutions (`Test #1`, `Review Test #1`, `Midterm Exam`, `Review Midterm`).
- `7 Simplified Slides`: 8 module summary docx files spanning the 7 core OOP topics.
- `8 Code Explained`: 48 walkthrough docx files explaining what each code example does, the underlying concept, walkthrough, and exam traps.
- Root: `CST3513_OOP_Study_Plan.pdf` (2-day crash study plan).

---

## Study Modes (Menu)

1. **Predict the Output**
   - Picks a runnable snippet from `4 Code Examples` across the selected topic.
   - Hides the output completely until you type your prediction.
   - Compiles and runs the snippet with your real JDK `javac`/`java` and displays a character-accurate diff.
   - If incorrect, triggers the one-line Cheat Sheet rule prompt.

2. **Does It Compile?**
   - Takes working snippets and with 50% probability injects realistic syntax/OOP bugs (e.g., missing `super()`, calling instance members from static `main`, improper method signatures, lossy conversions, private access violations).
   - Asks whether it compiles, what it prints, or what error it produces.
   - Truly compiles with `javac` and displays real compiler diagnostics.

3. **Write from Memory**
   - Displays the task specifications and concepts extracted from `8 Code Explained`.
   - Completely conceals the reference code.
   - Provides an in-browser code editor to paste/type your solution.
   - Compiles and executes your code against real tests, then provides side-by-side comparison with the course reference implementation.

4. **Exam Questions (Cold Practice)**
   - Extracts real numbered questions from past exam papers (`Test #1`, `Midterm Exam`, etc.).
   - Keeps official keys locked on the server until you type and submit your answer.
   - Unlocks the official exam key for self-grading.

5. **Flashcards & Spaced Repetition (1, 3, 7, 14 days)**
   - Includes 85+ pre-extracted core OOP rules from `7 Simplified Slides` and `8 Code Explained`.
   - Spaced repetition algorithm schedules cards at 1, 3, 7, and 14 days upon success; resets to 1 day on missed cards.
   - Allows adding your own custom rules anytime.

6. **Targeted Weak-Spot Mode**
   - Continuously monitors your accuracy per topic in SQLite.
   - Dynamically targets the topic with your lowest accuracy or highest mistake count.

---

## Tracking & SQLite Persistence

- **Attempt Logging**: Every exercise attempt records `exercise_type`, `topic`, `item_title`, `user_answer`, `expected_answer`, `is_correct`, and `timestamp` into SQLite (`study_tool.db`).
- **Dashboard**: Live accuracy percentage per topic, current streak counter 🔥, due flashcard count, and full indexed course summary.
- **Cheat Sheet Prompt**: After any wrong answer across all study modes, a prompt appears asking for a one-line rule to lock the concept in. The rule is saved to your cheat sheet and automatically scheduled for review in flashcards tomorrow.

---

## JDK Requirement & Detection

The tool automatically checks for a working JDK on startup:
- Probes `PATH`, `JAVA_HOME`, `/Library/Java/JavaVirtualMachines/`, and Homebrew Cellar.
- If missing, it outputs detailed instructions:
  - Install via Homebrew: `brew install openjdk`
  - Or install Eclipse Temurin (Java 21 LTS) from https://adoptium.net
  - Export `JAVA_HOME` in `~/.zshrc`.
