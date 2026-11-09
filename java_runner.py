"""
Java Runner & JDK Detector for CST 3513 OOP Study Tool
Handles:
1. JDK detection on startup with diagnostic fix instructions.
2. Compilation and execution of Java snippets safely with timeouts.
3. Realistic Java OOP bug mutation for "Does it compile?" mode.
"""

import os
import glob
import re
import subprocess
import tempfile
import random
from typing import Dict, Any, List, Tuple, Optional

class JavaRunner:
    def __init__(self):
        self.jdk_info = self.detect_jdk()
        self.javac_path = self.jdk_info.get("javac")
        self.java_path = self.jdk_info.get("java")
        self.is_ready = self.jdk_info.get("found", False)

    @staticmethod
    def detect_jdk() -> Dict[str, Any]:
        """Probes PATH, JAVA_HOME, and standard macOS paths for a working JDK."""
        # 1. Try PATH
        try:
            r = subprocess.run(["javac", "-version"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                v = (r.stdout or r.stderr).strip()
                return {
                    "found": True,
                    "javac": "javac",
                    "java": "java",
                    "version": v,
                    "location": "System PATH"
                }
        except Exception:
            pass

        # 2. Try JAVA_HOME and known macOS directories
        candidates = []
        if "JAVA_HOME" in os.environ:
            candidates.append(os.path.join(os.environ["JAVA_HOME"], "bin"))
        candidates.extend(glob.glob("/Library/Java/JavaVirtualMachines/*/Contents/Home/bin"))
        candidates.extend(glob.glob("/opt/homebrew/opt/openjdk*/bin"))
        candidates.extend(glob.glob("/opt/homebrew/Cellar/openjdk*/*/bin"))
        candidates.extend(glob.glob("/usr/local/opt/openjdk*/bin"))

        for c in candidates:
            javac_bin = os.path.join(c, "javac")
            java_bin = os.path.join(c, "java")
            if os.path.isfile(javac_bin) and os.access(javac_bin, os.X_OK):
                try:
                    r = subprocess.run([javac_bin, "-version"], capture_output=True, text=True, timeout=5)
                    if r.returncode == 0:
                        v = (r.stdout or r.stderr).strip()
                        # Set JAVA_HOME and PATH for the current process
                        jdk_home = os.path.dirname(c)
                        os.environ["JAVA_HOME"] = jdk_home
                        os.environ["PATH"] = f"{c}:{os.environ.get('PATH', '')}"
                        return {
                            "found": True,
                            "javac": javac_bin,
                            "java": java_bin,
                            "version": v,
                            "location": c
                        }
                except Exception:
                    continue

        return {
            "found": False,
            "error": "No working JDK detected on this machine.",
            "fix_instructions": (
                "A Java Development Kit (JDK) is required to compile and run snippets.\n\n"
                "To fix on macOS:\n"
                "  1. Install via Homebrew: brew install openjdk\n"
                "     sudo ln -sfn /opt/homebrew/opt/openjdk/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk\n\n"
                "  2. Or download Eclipse Temurin (Java 21 LTS) from https://adoptium.net\n\n"
                "  3. Set JAVA_HOME in your ~/.zshrc or ~/.bash_profile:\n"
                "     export JAVA_HOME=$(/usr/libexec/java_home 2>/dev/null || echo '/opt/homebrew/opt/openjdk')\n"
                "     export PATH=\"$JAVA_HOME/bin:$PATH\""
            )
        }

    @staticmethod
    def extract_java_classes(text: str) -> List[Tuple[str, str]]:
        """
        Parses Java classes from a snippet by tracking balanced curly braces.
        Returns list of (ClassName, ClassCode).
        """
        # Strip output section if present
        parts = re.split(r'\n\s*(?:run\s*:|\s*BUILD SUCCESSFUL|Output\s*:)', text, flags=re.IGNORECASE)
        code_part = parts[0]

        classes = []
        pattern = re.compile(r'(?:public\s+|abstract\s+|final\s+)*class\s+([A-Za-z0-9_]+)[^{]*\{')
        pos = 0
        while True:
            m = pattern.search(code_part, pos)
            if not m:
                break
            start_idx = m.start()
            cname = m.group(1)
            brace_idx = m.end() - 1
            depth = 1
            i = brace_idx + 1
            while i < len(code_part) and depth > 0:
                ch = code_part[i]
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                i += 1
            class_code = code_part[start_idx:i]
            classes.append((cname, class_code))
            pos = i

        return classes

    def compile_and_run(self, raw_code: str, stdin_input: str = "", timeout_sec: int = 5) -> Dict[str, Any]:
        """
        Takes raw Java code (which may contain multiple classes or a single class),
        saves each class to its respective .java file in a temp directory, compiles,
        and runs the main class.
        """
        if not self.is_ready:
            return {
                "compiled": False,
                "error": "JDK is not installed or configured.\n" + self.jdk_info.get("fix_instructions", ""),
                "output": "",
                "exit_code": -1
            }

        classes = self.extract_java_classes(raw_code)
        
        # If no classes parsed via brace matching, try wrapping as a simple Main class if main method exists
        with tempfile.TemporaryDirectory() as tmpdir:
            file_paths = []
            main_class = None

            if not classes:
                # Check if it has a class keyword or just loose statements
                if "class " in raw_code:
                    # Fallback: single Main.java or first class match
                    m = re.search(r'class\s+([A-Za-z0-9_]+)', raw_code)
                    cname = m.group(1) if m else "Main"
                else:
                    cname = "Main"
                    raw_code = f"public class Main {{\n    public static void main(String[] args) {{\n{raw_code}\n    }}\n}}"
                
                clean_code = re.sub(r'package\s+[\w\.]+;\s*', '', raw_code)
                jpath = os.path.join(tmpdir, f"{cname}.java")
                with open(jpath, "w", encoding="utf-8") as f:
                    f.write(clean_code)
                file_paths.append(jpath)
                main_class = cname
            else:
                for cname, code in classes:
                    # Strip package declarations so everything runs cleanly in default package
                    clean_code = re.sub(r'package\s+[\w\.]+;\s*', '', code)
                    jpath = os.path.join(tmpdir, f"{cname}.java")
                    with open(jpath, "w", encoding="utf-8") as f:
                        f.write(clean_code)
                    file_paths.append(jpath)
                    if "static void main" in code or "static public void main" in code:
                        main_class = cname

            if not main_class and classes:
                # Default to last class or class containing Main
                for cname, _ in classes:
                    if "main" in cname.lower() or "app" in cname.lower() or "demo" in cname.lower():
                        main_class = cname
                        break
                if not main_class:
                    main_class = classes[-1][0]

            # Compile
            compile_cmd = [self.javac_path] + file_paths
            try:
                c_proc = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=10)
            except subprocess.TimeoutExpired:
                return {
                    "compiled": False,
                    "error": "Compilation timed out (took > 10s).",
                    "output": "",
                    "exit_code": -1
                }
            except Exception as e:
                return {
                    "compiled": False,
                    "error": f"Failed to run javac: {str(e)}",
                    "output": "",
                    "exit_code": -1
                }

            if c_proc.returncode != 0:
                # Filter file paths to make error message friendly
                clean_err = c_proc.stderr.replace(tmpdir + "/", "")
                return {
                    "compiled": False,
                    "error": clean_err.strip(),
                    "output": "",
                    "exit_code": c_proc.returncode
                }

            # Run
            if not main_class:
                return {
                    "compiled": True,
                    "error": "Compiled successfully, but no 'public static void main' entrypoint found to run.",
                    "output": "",
                    "exit_code": 0
                }

            run_cmd = [self.java_path, "-cp", tmpdir, main_class]
            try:
                r_proc = subprocess.run(
                    run_cmd,
                    input=stdin_input,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec
                )
                output = r_proc.stdout
                if r_proc.stderr:
                    output += "\n" + r_proc.stderr
                return {
                    "compiled": True,
                    "error": "" if r_proc.returncode == 0 else f"Runtime exit code: {r_proc.returncode}",
                    "output": output.strip(),
                    "exit_code": r_proc.returncode
                }
            except subprocess.TimeoutExpired:
                return {
                    "compiled": True,
                    "error": f"Execution timed out (> {timeout_sec}s). Possible infinite loop or waiting for input.",
                    "output": "",
                    "exit_code": -1
                }
            except Exception as e:
                return {
                    "compiled": True,
                    "error": f"Failed to run java: {str(e)}",
                    "output": "",
                    "exit_code": -1
                }

    def inject_bug(self, code: str) -> Tuple[str, bool, str, str]:
        """
        Takes working Java code and with 50% probability injects one subtle bug.
        Returns:
            mutated_code (str)
            has_bug (bool)
            bug_type (str)
            explanation (str)
        """
        # 50% chance of leaving it unmodified (tests "Yes it compiles")
        if random.random() < 0.35:
            return code, False, "none", "The code is completely valid and compiles without errors."

        mutations = []

        # 1. Remove super(...) or super call
        super_match = re.search(r'\bsuper\s*\([^)]*\)\s*;', code)
        if super_match:
            def mut_super(c):
                return c.replace(super_match.group(0), "// super call removed", 1)
            mutations.append((
                mut_super,
                "remove_super",
                "Removed super(...) constructor invocation in a subclass where the superclass requires constructor arguments."
            ))

        # 2. Call instance method/variable from static main context directly without instance
        # e.g., obj.getVal() -> getVal()
        call_match = re.search(r'\b([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\s*\(\s*\)', code)
        if call_match and call_match.group(1) not in ("System", "Math", "Integer", "Double", "Arrays"):
            obj_name = call_match.group(1)
            method_name = call_match.group(2)
            def mut_static(c):
                return c.replace(f"{obj_name}.{method_name}()", f"{method_name}()", 1)
            mutations.append((
                mut_static,
                "static_context_error",
                f"Calling instance method '{method_name}()' directly from static context without specifying instance '{obj_name}'."
            ))

        # 3. Add accidental semicolon right after method or constructor header
        header_match = re.search(r'(public|protected|private)?\s*(?:static\s+)?(?:[\w<>\[\]]+\s+)?([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{', code)
        if header_match:
            hdr = header_match.group(0)
            mutated_hdr = hdr[:-1].rstrip() + "; {"
            def mut_semi(c):
                return c.replace(hdr, mutated_hdr, 1)
            mutations.append((
                mut_semi,
                "semicolon_after_method_header",
                "Placed an illegal semicolon ';' directly after the method/constructor declaration header."
            ))

        # 4. Change return type of a getter from expected type to void while still returning a value
        getter_match = re.search(r'public\s+(int|double|String|boolean)\s+get([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{', code)
        if getter_match:
            old_hdr = getter_match.group(0)
            new_hdr = old_hdr.replace(getter_match.group(1), "void", 1)
            def mut_ret(c):
                return c.replace(old_hdr, new_hdr, 1)
            mutations.append((
                mut_ret,
                "void_returning_value",
                f"Changed method return type to 'void' but kept the return statement inside the body."
            ))

        # 5. Incompatible assignment: double assigned to int without cast
        assign_match = re.search(r'\bint\s+([A-Za-z0-9_]+)\s*=\s*([0-9]+\.[0-9]+)\s*;', code)
        if assign_match:
            pass # already double to int
        else:
            # Change an int assignment to double literal, e.g. int x = 5; -> int x = 5.5;
            int_match = re.search(r'\bint\s+([A-Za-z0-9_]+)\s*=\s*(\d+)\s*;', code)
            if int_match:
                orig_int = int_match.group(0)
                bad_int = orig_int.replace(int_match.group(2), f"{int_match.group(2)}.5", 1)
                def mut_type(c):
                    return c.replace(orig_int, bad_int, 1)
                mutations.append((
                    mut_type,
                    "lossy_conversion",
                    "Assigned floating-point value (double) to an 'int' variable without explicit type casting (possible lossy conversion)."
                ))

        # 6. Change private field access
        priv_match = re.search(r'private\s+[\w<>\[\]]+\s+([A-Za-z0-9_]+)\s*;', code)
        if priv_match:
            fname = priv_match.group(1)
            # Find an instance access and replace with direct field access
            call_match = re.search(rf'\b([a-zA-Z0-9_]+)\.set[A-Za-z0-9_]+\s*\(([^)]+)\)', code)
            if call_match:
                obj = call_match.group(1)
                val = call_match.group(2)
                def mut_priv(c):
                    return c.replace(call_match.group(0), f"{obj}.{fname} = {val}", 1)
                mutations.append((
                    mut_priv,
                    "private_access_violation",
                    f"Directly accessed private field '{fname}' from another class instead of using accessor/mutator methods."
                ))

        if not mutations:
            # Fallback simple syntax bug: remove a semicolon
            semi_match = re.search(r';\s*\n', code)
            if semi_match:
                def mut_fallback(c):
                    return c[:semi_match.start()] + "\n" + c[semi_match.end():]
                mutations.append((
                    mut_fallback,
                    "missing_semicolon",
                    "Omitted a required semicolon at the end of a statement."
                ))

        if not mutations:
            return code, False, "none", "The code compiles without errors."

        selected_mut, btype, explanation = random.choice(mutations)
        try:
            mutated_code = selected_mut(code)
            return mutated_code, True, btype, explanation
        except Exception:
            return code, False, "none", "The code compiles without errors."
