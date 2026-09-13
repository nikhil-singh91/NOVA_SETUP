"""Code scaffolding, project generation, and VS Code integration."""

from __future__ import annotations

from pathlib import Path

from core.logger import get_logger
from core.registry import registry

from desktop.apps import AppLauncher
from desktop.files import FileSystemManager
from desktop.models import DesktopActionType, DesktopResult
from desktop.safety import DesktopSafetyPolicy

logger = get_logger(__name__)


class CodeProjectManager:
    """Creates multi-file code scaffolds, generates code via ProviderManager, and opens projects in VS Code."""

    BOILERPLATES: dict[str, dict[str, str]] = {
        "web": {
            "index.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NOVA Web Project</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <h1>Welcome to Your Project</h1>
        <p>Created automatically with NOVA Desktop Actions.</p>
        <button id="actionBtn">Click Me</button>
    </div>
    <script src="app.js"></script>
</body>
</html>""",
            "style.css": """* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f172a;
    color: #f8fafc;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
}
.container {
    text-align: center;
    padding: 2rem;
    background: #1e293b;
    border-radius: 12px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
}
button {
    margin-top: 1.5rem;
    padding: 0.75rem 1.5rem;
    background: #3b82f6;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
}
button:hover {
    background: #2563eb;
}""",
            "app.js": """document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("actionBtn");
    btn.addEventListener("click", () => {
        alert("Hello from NOVA!");
    });
});""",
        },
        "cpp": {
            "main.cpp": """#include <iostream>
#include <vector>

int main() {
    std::cout << "Hello from NOVA C++ Project!" << std::endl;
    return 0;
}""",
        },
        "python": {
            "main.py": """# Python Program created by NOVA Desktop Actions

def main():
    print("Hello from NOVA Python Project!")

if __name__ == "__main__":
    main()
""",
        },
    }

    @classmethod
    def generate_code_content(cls, prompt: str, language: str = "python") -> str:
        """Generate high-quality source code for custom requested logic."""
        if registry.exists("provider_manager"):
            try:
                provider_mgr = registry.get("provider_manager")
                ai_prompt = (
                    f"Write clean, idiomatic {language} code for the following request:\n"
                    f"\"{prompt}\"\n\n"
                    f"Rules: Output ONLY executable {language} code. No markdown code blocks, explanations, or commentary."
                )
                res = provider_mgr.generate(ai_prompt)
                if res and res.text:
                    clean = res.text.strip()
                    if clean.startswith("```"):
                        lines = clean.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        clean = "\n".join(lines)
                    return clean
            except Exception as exc:
                logger.warning("Code generation via provider failed: %s", exc)

        # Fallback templates
        if "calculator" in prompt.lower():
            return """# Simple Interactive Calculator

def add(x, y): return x + y
def subtract(x, y): return x - y
def multiply(x, y): return x * y
def divide(x, y): return x / y if y != 0 else "Error: Division by zero"

def main():
    print("=== Simple Calculator ===")
    print("1. Add | 2. Subtract | 3. Multiply | 4. Divide")
    choice = input("Enter choice (1-4): ")
    num1 = float(input("Enter first number: "))
    num2 = float(input("Enter second number: "))
    
    if choice == '1': print(f"Result: {add(num1, num2)}")
    elif choice == '2': print(f"Result: {subtract(num1, num2)}")
    elif choice == '3': print(f"Result: {multiply(num1, num2)}")
    elif choice == '4': print(f"Result: {divide(num1, num2)}")
    else: print("Invalid Input")

if __name__ == "__main__":
    main()
"""
        elif "binary search" in prompt.lower() and "c++" in language.lower():
            return """#include <iostream>
#include <vector>

int binarySearch(const std::vector<int>& arr, int target) {
    int left = 0;
    int right = arr.size() - 1;
    while (left <= right) {
        int mid = left + (right - left) / 2;
        if (arr[mid] == target) return mid;
        if (arr[mid] < target) left = mid + 1;
        else right = mid - 1;
    }
    return -1;
}

int main() {
    std::vector<int> data = {1, 3, 5, 7, 9, 11, 13, 15};
    int target = 7;
    int result = binarySearch(data, target);
    std::cout << "Target " << target << (result != -1 ? " found at index " : " not found.") << result << std::endl;
    return 0;
}
"""

        return f"# {language.title()} project starter\nprint('Ready to code!')\n"

    @classmethod
    def create_project(
        cls,
        project_name: str,
        template_type: str = "web",
        custom_files: list[str] | None = None,
        custom_prompt: str = "",
        open_in_vscode: bool = True,
        parent_dir: Path | None = None,
    ) -> DesktopResult:
        """Create a multi-file project and optionally open it in Visual Studio Code."""
        base_dir = parent_dir or DesktopSafetyPolicy.get_default_workspace()
        project_dir = (base_dir / project_name).resolve()
        project_dir.mkdir(parents=True, exist_ok=True)

        files_to_create: dict[str, str] = {}

        if template_type in cls.BOILERPLATES:
            files_to_create.update(cls.BOILERPLATES[template_type])

        if custom_files:
            for f in custom_files:
                if f not in files_to_create:
                    ext = Path(f).suffix.lower()
                    lang = "python" if ext == ".py" else "cpp" if ext in (".cpp", ".hpp") else "javascript" if ext == ".js" else "text"
                    code_body = cls.generate_code_content(custom_prompt or f"Create {f}", language=lang) if custom_prompt else f"// File: {f}\n"
                    files_to_create[f] = code_body

        success, created_paths, msg = FileSystemManager.create_files(
            list(files_to_create.keys()),
            parent=project_dir,
            content_map=files_to_create,
            overwrite=True,
        )

        if not success:
            return DesktopResult(
                success=False,
                action_type=DesktopActionType.CREATE_CODE_PROJECT,
                error=f"Failed to create project files: {msg}",
                spoken_response="Sorry Boss, I couldn't create the project files.",
            )

        if open_in_vscode:
            AppLauncher.launch("Visual Studio Code", project_dir)

        spoken = f"Created {project_name} project with {len(created_paths)} files" + (" and opened in VS Code." if open_in_vscode else ".")
        return DesktopResult(
            success=True,
            action_type=DesktopActionType.CREATE_CODE_PROJECT,
            message=f"Created project '{project_name}' at '{project_dir}'.",
            spoken_response=spoken,
            target_path=str(project_dir),
            metadata={"project_name": project_name, "project_dir": str(project_dir), "files": [p.name for p in created_paths]},
        )
