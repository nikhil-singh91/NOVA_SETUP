"""AI document writing and text editor integration for letters, essays, and notes."""

from __future__ import annotations

from pathlib import Path

from core.environment import environment_observer
from core.logger import get_logger
from core.registry import registry

from desktop.apps import AppLauncher
from desktop.files import FileSystemManager
from desktop.models import DesktopActionType, DesktopResult
from desktop.safety import DesktopSafetyPolicy

logger = get_logger(__name__)


class DocumentEditor:
    """Coordinates AI text generation, code drafting, and text editor file writing."""

    CODE_FALLBACKS: dict[str, str] = {
        "bubble_sort_cpp": """#include <iostream>
#include <vector>

void bubbleSort(std::vector<int>& arr) {
    int n = arr.size();
    for (int i = 0; i < n - 1; ++i) {
        for (int j = 0; j < n - i - 1; ++j) {
            if (arr[j] > arr[j + 1]) {
                std::swap(arr[j], arr[j + 1]);
            }
        }
    }
}

int main() {
    std::vector<int> arr = {64, 34, 25, 12, 22, 11, 90};
    bubbleSort(arr);
    std::cout << "Sorted array: ";
    for (int x : arr) std::cout << x << " ";
    std::cout << std::endl;
    return 0;
}
""",
        "bubble_sort_python": """def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

if __name__ == "__main__":
    sample = [64, 34, 25, 12, 22, 11, 90]
    print("Original:", sample)
    print("Sorted:", bubble_sort(sample))
""",
        "reverse_string_python": """def reverse_string(s: str) -> str:
    return s[::-1]

if __name__ == "__main__":
    text = "Hello World"
    print("Original:", text)
    print("Reversed:", reverse_string(text))
""",
        "reverse_array_cpp": """#include <iostream>
#include <vector>
#include <algorithm>

int main() {
    std::vector<int> arr = {1, 2, 3, 4, 5};
    std::reverse(arr.begin(), arr.end());
    std::cout << "Reversed array: ";
    for (int x : arr) std::cout << x << " ";
    std::cout << std::endl;
    return 0;
}
""",
    }

    @classmethod
    def generate_document_text(cls, topic_or_prompt: str) -> str:
        """Generate well-structured document or code text."""
        topic_lower = topic_or_prompt.lower().strip()

        # 1. Literal short text phrases (e.g. "hello", "what is love", "this is my first program")
        if topic_lower in ["hello", "what is love", "this is my first program", "hello world", "welcome"]:
            return topic_or_prompt

        # 2. Check if code generation is requested
        is_code = any(k in topic_lower for k in ["bubble sort", "sort", "reverse", "code", "program", "c++", "cpp", "python", "javascript", "function", "class", "algorithm"])

        # Try LLM provider generation
        if registry.exists("provider_manager"):
            try:
                provider_mgr = registry.get("provider_manager")
                if is_code:
                    prompt = (
                        f"Write clean, complete, and syntax-valid code for the following request:\n"
                        f"\"{topic_or_prompt}\"\n\n"
                        f"Rules: Return ONLY the code itself with no markdown backticks, no explanations, and no commentary."
                    )
                    system_instruction = "You are an expert software engineer. Output only executable code with no markdown formatting."
                else:
                    prompt = (
                        f"Write a clean, professional, and well-formatted document for:\n"
                        f"\"{topic_or_prompt}\"\n\n"
                        f"Rules: Provide only the final document text without meta-commentary, markdown wrapping, or preamble."
                    )
                    system_instruction = "You are a professional document writer. Generate clean, formal text with no conversational filler."

                generated = provider_mgr.generate_response(
                    prompt=prompt,
                    system_prompt=system_instruction,
                    task_type="code" if is_code else "general",
                )
                if generated and generated.strip():
                    cleaned = generated.strip()
                    # Strip any markdown fences if model returned them
                    if cleaned.startswith("```") and cleaned.endswith("```"):
                        lines = cleaned.splitlines()
                        cleaned = "\n".join(lines[1:-1]).strip()
                    return cleaned
            except Exception as exc:
                logger.warning("Provider generation failed for document, using fallback: %s", exc)

        # 3. Code Fallbacks
        if "bubble sort" in topic_lower:
            if "c++" in topic_lower or "cpp" in topic_lower:
                return cls.CODE_FALLBACKS["bubble_sort_cpp"]
            return cls.CODE_FALLBACKS["bubble_sort_python"]

        if "reverse" in topic_lower and "string" in topic_lower:
            return cls.CODE_FALLBACKS["reverse_string_python"]

        if "reverse" in topic_lower and "array" in topic_lower:
            return cls.CODE_FALLBACKS["reverse_array_cpp"]

        # 4. Template fallbacks for documents
        if "icpc" in topic_lower:
            return (
                "ICPC (International Collegiate Programming Contest)\n\n"
                "Overview:\n"
                "The International Collegiate Programming Contest is an algorithmic programming contest for college students. "
                "Teams of three, representing their university, work to solve algorithmic problems, fostering collaboration, "
                "creativity, innovation, and the ability to perform under pressure.\n\n"
                "Format:\n"
                "- Teams: 3 students per team using 1 computer.\n"
                "- Duration: 5 hours.\n"
                "- Languages: C++, Java, Python, Kotlin, C.\n"
                "- Scoring: Ranked by number of problems solved and total penalty time."
            )

        if "leave application" in topic_lower or "leave" in topic_lower:
            return (
                "Subject: Application for Leave of Absence\n\n"
                "Respected Sir/Madam,\n\n"
                "I am writing this application to formally request leave of absence from college / classes due to personal reasons / illness. "
                "I kindly request you to approve my leave for the required duration. "
                "I will make sure to catch up with all missed lectures and assignments upon my return.\n\n"
                "Thanking you.\n\n"
                "Yours obediently,\n"
                "[Your Name]\n"
                "Student ID / Roll No."
            )

        return topic_or_prompt

    @classmethod
    def write_and_open_document(
        cls,
        topic: str,
        filename: str = "document.txt",
        parent_dir: Path | None = None,
        open_in_editor: bool = True,
        destination: str = "Notepad",
    ) -> DesktopResult:
        """Generate document content, write to file, and open in macOS TextEdit/Notepad."""
        base_dir = parent_dir or DesktopSafetyPolicy.get_default_workspace()
        clean_filename = filename.strip()

        # Adjust filename extension based on topic
        t_lower = topic.lower()
        if "c++" in t_lower or "cpp" in t_lower:
            if not clean_filename.endswith(".cpp"):
                clean_filename = clean_filename.rsplit(".", 1)[0] + ".cpp"
        elif "python" in t_lower:
            if not clean_filename.endswith(".py"):
                clean_filename = clean_filename.rsplit(".", 1)[0] + ".py"
        elif not clean_filename.endswith((".txt", ".md", ".rtf", ".doc", ".cpp", ".py", ".js")):
            clean_filename += ".txt"

        content = cls.generate_document_text(topic)
        success, paths, msg = FileSystemManager.create_files(
            [clean_filename],
            parent=base_dir,
            content_map={clean_filename: content},
            overwrite=True,
        )

        if not success or not paths or not paths[0].exists():
            return DesktopResult(
                success=False,
                action_type=DesktopActionType.WRITE_DOCUMENT,
                error=f"Could not create document file: {msg}",
                spoken_response="Sorry Boss, I couldn't write the document file.",
            )

        doc_path = paths[0]
        if open_in_editor:
            AppLauncher.launch("TextEdit", doc_path)

        environment_observer.update_action_context(
            action="GENERATE_AND_WRITE_DOCUMENT",
            created_path=doc_path,
            opened_target=str(doc_path),
        )

        # On macOS, TextEdit is the native editor unless Notepad is explicitly named
        dest_label = "Notepad" if destination and destination.strip().lower() == "notepad" else "TextEdit"
        if any(k in t_lower for k in ["code", "program", "bubble sort", "reverse", "python", "c++", "cpp"]):
            spoken = f"Done Boss. I wrote the {topic} and opened it in {dest_label}."
        elif "leave" in t_lower or "application" in t_lower or "letter" in t_lower or "essay" in t_lower or "document" in t_lower:
            spoken = f"I've written the {topic} and opened it in {dest_label}."
        else:
            spoken = f"Done Boss. I wrote it in {dest_label}."

        return DesktopResult(
            success=True,
            action_type=DesktopActionType.WRITE_DOCUMENT,
            message=f"Created and opened document at '{doc_path}'.",
            spoken_response=spoken,
            target_path=str(doc_path),
            metadata={
                "filename": clean_filename,
                "doc_path": str(doc_path),
                "destination": dest_label,
                "content_bytes": doc_path.stat().st_size if doc_path.exists() else len(content),
            },
        )
