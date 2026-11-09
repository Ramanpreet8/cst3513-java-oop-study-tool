#!/usr/bin/env bash
# CST 3513 Java OOP Study Tool launcher
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "Error: Python 3 is required."
    exit 1
fi

COURSE_PATH="$DIR/course_materials/CST 3513 Java OOP"

# If first argument is an existing directory, use it as course path
if [ $# -gt 0 ] && [ -d "$1" ]; then
    COURSE_PATH="$1"
    shift
fi

exec "$PYTHON_BIN" "$DIR/app.py" --course-dir "$COURSE_PATH" "$@"
