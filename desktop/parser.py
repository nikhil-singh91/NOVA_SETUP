"""Natural language parser mapping user voice commands to structured DesktopActionPlan and DesktopTaskPlan."""

from __future__ import annotations

import re

from core.logger import get_logger

from desktop.models import (
    DesktopActionPlan,
    DesktopActionType,
    DesktopStep,
    DesktopTaskPlan,
)

logger = get_logger(__name__)


class DesktopIntentParser:
    """Parses natural desktop, file, folder, project, and camera commands into actionable plans."""

    @classmethod
    def parse(cls, text: str) -> DesktopActionPlan | DesktopTaskPlan | None:
        """Parse natural user command into a single plan or multi-step task plan."""
        from intent.normalizer import TextNormalizer
        norm = TextNormalizer.normalize(text)
        raw = norm.raw
        lower = norm.cleaned_lower

        # 1. STOP / CANCEL
        if lower in ["stop desktop task", "cancel desktop task", "stop creating files", "cancel the task", "stop"]:
            return DesktopActionPlan(action_type=DesktopActionType.STOP_DESKTOP_TASK, raw_prompt=raw)

        # 2. CAMERA COMMANDS
        if any(p in lower for p in ["take a picture", "click a picture", "click my picture", "take my photo", "take photo", "photo kheencho", "tasveer lo"]):
            return DesktopActionPlan(action_type=DesktopActionType.TAKE_PHOTO, raw_prompt=raw)

        if lower in ["open camera", "open the camera", "camera kholo", "launch camera"]:
            return DesktopActionPlan(action_type=DesktopActionType.OPEN_CAMERA, raw_prompt=raw)

        # 3. COMPOSITE / MULTI-STEP COMMANDS
        if any(k in lower for k in ["and create", "then create", "and write", "folder with", "project called", "then open"]) or (
            ("folder called" in lower or "make a folder" in lower or "create a folder" in lower) and ("create" in lower and "inside" in lower)
        ):
            multi_plan = cls._parse_multi_step_or_tree(raw, lower)
            if multi_plan:
                return multi_plan

        # 4. RENAME FILES / FOLDERS ("Rename my DSA folder to DSA Practice", "Rename a.cpp to tree.cpp", "Change the name of Test to TestProject")
        m_rename = re.search(
            r"^(?:rename|change\s+(?:the\s+)?name\s+of)\s+(?:my\s+|the\s+)?(.+?)\s+(?:to|into|as)\s+([a-zA-Z0-9_\-\.\s]+)$",
            lower,
        )
        if m_rename:
            old_name = m_rename.group(1).strip()
            new_name = m_rename.group(2).strip()
            for suffix in [" folder", " directory", " file"]:
                if old_name.endswith(suffix):
                    old_name = old_name[:-len(suffix)].strip()
            return DesktopActionPlan(
                action_type=DesktopActionType.RENAME_ITEM,
                target_name=old_name,
                metadata={"new_name": new_name},
                raw_prompt=raw,
            )

        # 5. DELETE COMMANDS ("Delete Test", "Delete my Test folder", "Remove a.cpp", "Delete TestProject", "Delete this")
        m_del = re.search(
            r"^(?:please\s+)?(?:delete|remove|trash|hatao|delete\s+karo)\s+(?:my\s+|the\s+)?(.+?)(?:\s+from\s+(?:the\s+|my\s+)?(desktop|documents|downloads))?$",
            lower,
        )
        if m_del:
            target = m_del.group(1).strip()
            loc = m_del.group(2).strip() if m_del.group(2) else ""
            for suffix in [" folder", " directory", " file"]:
                if target.endswith(suffix):
                    target = target[:-len(suffix)].strip()
            if target in ["this", "that", "it", "this file", "this folder"]:
                return DesktopActionPlan(action_type=DesktopActionType.DELETE_ITEM, raw_prompt=raw)
            elif target:
                return DesktopActionPlan(
                    action_type=DesktopActionType.DELETE_ITEM,
                    target_name=target,
                    metadata={"location": loc} if loc else {},
                    raw_prompt=raw,
                )

        # 6. OPEN FILE IN APPLICATION ("Open a.cpp in VS Code", "Open index.html in VS Code", "Open my resume in Preview")
        m_open_in = re.search(
            r"^open\s+(?:my\s+|the\s+)?([a-zA-Z0-9_\-\.]+)\s+in\s+([a-zA-Z0-9_\-\s]+)$",
            lower,
        )
        if m_open_in:
            fname = m_open_in.group(1).strip()
            app = m_open_in.group(2).strip()
            if fname not in ("tab", "new tab", "browser", "folder", "camera"):
                return DesktopActionPlan(
                    action_type=DesktopActionType.OPEN_FILE,
                    target_name=fname,
                    app_name=app,
                    metadata={"app_name": app},
                    raw_prompt=raw,
                )

        # 7. FIND ITEM / WHERE IS ("Find my DSA folder", "Find NOVA_SETUP", "Where is my resume PDF?", "Find a.cpp", "Find my Python files")
        m_find = re.search(
            r"^(?:find\s+(?:and\s+open\s+)?|where\s+is\s+|show\s+me\s+(?:where\s+is\s+)?|search\s+(?:for\s+)?(?:my\s+)?)(?:my\s+|the\s+)?(.+?)(?:\s+folder|\s+file)?(?:\?)?$",
            lower,
        )
        if m_find:
            query = m_find.group(1).strip()
            is_and_open = "and open" in lower or lower.startswith("show me ")
            if query and not any(w in query for w in ["website", "site", "webpage", "google", "youtube", "weather", "news", "meaning"]):
                if is_and_open:
                    if "folder" in lower or query in ["downloads", "desktop", "documents"]:
                        return DesktopActionPlan(action_type=DesktopActionType.OPEN_FOLDER, target_name=query, raw_prompt=raw)
                    return DesktopActionPlan(action_type=DesktopActionType.OPEN_FILE, target_name=query, raw_prompt=raw)
                return DesktopActionPlan(action_type=DesktopActionType.FIND_ITEM, target_name=query, raw_prompt=raw)

        # 8. DOCUMENT & TEXT WRITING
        m_doc = re.search(r"^(?:open\s+(?:notepad|textedit|text\s+editor)\s+and\s+)?write\s+(?:a\s+|an\s+)?(.+?)(?:\s+in\s+notepad|\s+in\s+textedit)?$", lower)
        if m_doc and not any(c in lower for c in ["python", "c++", "cpp", "javascript", "code", "program", "script", "server", "calculator"]):
            topic = m_doc.group(1).strip()
            fname = "leave_application.txt" if "leave" in topic else f"{topic.replace(' ', '_')[:25]}.txt"
            return DesktopActionPlan(
                action_type=DesktopActionType.WRITE_DOCUMENT,
                content_topic=topic,
                file_names=[fname],
                raw_prompt=raw,
            )

        # 9. CODE FILE & PROGRAM WRITING
        m_code_file = re.search(r"^create\s+(?:a\s+)?(python|c\+\+|cpp|javascript|js|html)\s+(?:file|program|script)?\s+(?:and\s+)?(?:write\s+)?(.+)$", lower)
        if m_code_file:
            lang = m_code_file.group(1).strip()
            prompt = m_code_file.group(2).strip()
            ext = ".py" if "python" in lang else ".cpp" if "c++" in lang or "cpp" in lang else ".js"
            filename = f"calculator{ext}" if "calculator" in prompt else f"main{ext}"
            return DesktopActionPlan(
                action_type=DesktopActionType.WRITE_CODE_FILE,
                file_names=[filename],
                code_language=lang,
                content_topic=prompt,
                raw_prompt=raw,
            )

        # 10. CREATE MULTIPLE FILES / SINGLE FILE AT LOCATION
        # "Create three files a.cpp, b.cpp and c.cpp inside Test"
        # "Create index.html, style.css and app.js inside my project folder"
        # "Create a.cpp on Desktop"
        m_create_files_loc = re.search(
            r"^(?:create|make)\s+(?:(?:three|four|five|two|\d+)\s+files?\s+|file\s+|files?\s+)?(.+?)\s+(?:inside|in|on)\s+(?:the\s+|my\s+)?(.+?)(?:\s+folder|\s+directory)?$",
            lower,
        )
        if m_create_files_loc:
            files_part = m_create_files_loc.group(1).strip()
            loc_part = m_create_files_loc.group(2).strip()

            # Extract filenames
            tokens = [t.strip().strip(",") for t in re.split(r"[\s,]+|and\s+", files_part) if t.strip() and "." in t]
            if not tokens and ("." in files_part or "python file" in files_part):
                if "python file" in files_part:
                    m_py = re.search(r"called\s+([a-zA-Z0-9_\-\.]+)", files_part)
                    tokens = [m_py.group(1).strip()] if m_py else ["main.py"]
                else:
                    tokens = [files_part.replace("called", "").replace("named", "").strip()]

            if tokens:
                on_desktop = loc_part in ("desktop", "the desktop", "my desktop")
                return DesktopActionPlan(
                    action_type=DesktopActionType.CREATE_FILES,
                    file_names=tokens,
                    target_name=tokens[0],
                    metadata={"location": loc_part, "on_desktop": on_desktop, "parent_target": loc_part},
                    raw_prompt=raw,
                )

        # "Create files a.cpp b.cpp c.cpp", "Create files index.html style.css app.js"
        m_multi_files = re.search(r"^(?:create|make)\s+files?\s+(.+)$", lower)
        if m_multi_files:
            raw_files_str = m_multi_files.group(1).strip()
            tokens = [t.strip().strip(",") for t in re.split(r"[\s,]+|and\s+", raw_files_str) if t.strip() and "." in t]
            if tokens:
                return DesktopActionPlan(
                    action_type=DesktopActionType.CREATE_FILES,
                    file_names=tokens,
                    target_name=tokens[0],
                    raw_prompt=raw,
                )

        # "Create README.md", "Create index.html", "Create a.cpp"
        m_single_file = re.search(r"^(?:create|make)\s+(?:a\s+)?(?:file\s+(?:called|named)\s+|python\s+file\s+(?:called|named)\s+)?([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)$", norm.normalized, re.IGNORECASE)
        if m_single_file:
            fname = m_single_file.group(1).strip()
            return DesktopActionPlan(
                action_type=DesktopActionType.CREATE_FILES,
                file_names=[fname],
                target_name=fname,
                raw_prompt=raw,
            )

        # 11. CREATE FOLDER WITH EXPLICIT LOCATION
        # "Create a folder called DSA on Desktop", "Make a folder named College in Documents", "Create a folder called Trees inside my DSA folder"
        m_folder_loc = re.search(
            r"^(?:create|make)\s+(?:a\s+|a\s+new\s+)?(?:folder|directory)(?:\s+(?:called|named)\s+([a-zA-Z0-9_\-\s]+?))?\s+(?:on|in|inside)\s+(?:the\s+|my\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+folder|\s+directory)?$",
            norm.normalized,
            re.IGNORECASE,
        )
        if m_folder_loc:
            fname = m_folder_loc.group(1).strip() if m_folder_loc.group(1) else "NewFolder"
            loc = m_folder_loc.group(2).strip()
            on_desktop = loc.lower() in ("desktop", "the desktop", "my desktop")
            return DesktopActionPlan(
                action_type=DesktopActionType.CREATE_FOLDER,
                target_name=fname,
                metadata={"location": loc, "on_desktop": on_desktop},
                raw_prompt=raw,
            )

        # General Create Folder ("Create a folder called DSA", "Make a folder named Test")
        m_folder = re.search(
            r"^(?:create|make)\s+(?:a\s+|a\s+new\s+)?(?:folder|directory)\s+(?:called|named)\s+([a-zA-Z0-9_\-\s]+?)$",
            norm.normalized,
            re.IGNORECASE,
        )
        if m_folder:
            name = m_folder.group(1).strip()
            return DesktopActionPlan(
                action_type=DesktopActionType.CREATE_FOLDER,
                target_name=name,
                raw_prompt=raw,
            )

        # 12. OPEN FOLDER ("Open my DSA folder", "Open the Downloads folder", "Open it")
        if lower in ["open the folder i just created", "open the created folder", "open it", "open that folder"]:
            return DesktopActionPlan(
                action_type=DesktopActionType.OPEN_FOLDER,
                metadata={"use_context": True},
                raw_prompt=raw,
            )

        m_open_fld = re.search(r"^(?:open|show\s+me)\s+(?:the\s+|my\s+)?([a-zA-Z0-9_\-\s]+?)\s+(?:folder|directory)$", norm.normalized, re.IGNORECASE)
        if m_open_fld:
            fld_name = m_open_fld.group(1).strip()
            return DesktopActionPlan(
                action_type=DesktopActionType.OPEN_FOLDER,
                target_name=fld_name,
                raw_prompt=raw,
            )

        # 13. OPEN FILE ("Open a.cpp", "Open my resume.pdf", "Open my PDF")
        m_open_file = re.search(r"^open\s+(?:my\s+|the\s+)?([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)$", norm.normalized, re.IGNORECASE)
        if m_open_file:
            fname = m_open_file.group(1).strip()
            return DesktopActionPlan(
                action_type=DesktopActionType.OPEN_FILE,
                target_name=fname,
                raw_prompt=raw,
            )

        # 14. CLOSE APPLICATION
        m_close = re.search(r"^(?:close|quit|exit)\s+(?:my\s+)?(?:app\s+)?(.+)$", lower)
        if m_close:
            app_raw = m_close.group(1).strip()
            if app_raw not in ["tab", "window", "browser", "this", "it"]:
                return DesktopActionPlan(
                    action_type=DesktopActionType.CLOSE_APP,
                    app_name=app_raw,
                    raw_prompt=raw,
                )

        # 15. OPEN APPLICATION
        if not any(w in lower for w in ["website", "site", "webpage", "url", "tab", "camera", "photo", "folder", "file"]):
            m_open = re.search(r"^(?:open|launch|start)\s+(?:my\s+)?(?:app\s+|application\s+)?(.+?)(?:\s+app|\s+application)?$", lower)
            if m_open:
                app_raw = m_open.group(1).strip()
                from browser.sites.generic import TRUSTED_SITES

                is_explicit_app = "app" in lower or "application" in lower or lower.startswith("launch ")
                if app_raw.lower() in TRUSTED_SITES and not is_explicit_app:
                    pass
                elif app_raw not in ["tab", "new tab", "page", "dsa folder", "it", "this"]:
                    return DesktopActionPlan(
                        action_type=DesktopActionType.OPEN_APP,
                        app_name=app_raw,
                        raw_prompt=raw,
                    )

        # 16. WRITE COMMAND / WRITE DOCUMENT
        m_write = re.search(r"^(?:open\s+(?:the\s+)?(?:notepad|textedit|text\s+editor)\s+and\s+)?write\s+(?:a\s+|an\s+)?(.+?)(?:\s+in\s+notepad|\s+in\s+textedit)?$", norm.normalized, re.IGNORECASE)
        if m_write and not any(q in lower for q in ["how to", "how do i", "what is write", "why write"]):
            topic = m_write.group(1).strip()
            return DesktopActionPlan(
                action_type=DesktopActionType.WRITE_DOCUMENT,
                content_topic=topic,
                target_name="document.txt",
                raw_prompt=raw,
            )

        return None

    @classmethod
    def _parse_multi_step_or_tree(cls, raw: str, lower: str) -> DesktopTaskPlan | None:
        """Parse composite multi-action phrases into a structured DesktopTaskPlan."""
        # Case A: "Create a project called Demo on Desktop with index.html, style.css and app.js"
        # "Create a folder called DSA on Desktop with a.cpp, b.cpp and c.cpp"
        # "Create a DSA folder with Arrays, LinkedList and Trees"
        m_proj_files = re.search(
            r"create\s+(?:a\s+)?(?:project|folder)?(?:\s+(?:called|named))?\s*([a-zA-Z0-9_\-]+)\s+(?:folder\s+)?(?:on\s+(?:the\s+|my\s+)?(desktop|documents|downloads)\s+)?with\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if m_proj_files:
            folder_name = m_proj_files.group(1).strip()
            loc = m_proj_files.group(2).strip().lower() if m_proj_files.group(2) else "desktop"
            raw_files = m_proj_files.group(3).strip()
            tokens = [t.strip().strip(",") for t in re.split(r"[\s,]+|and\s+", raw_files) if t.strip() and "." in t]
            if not tokens:
                tokens = [t.strip().title() for t in re.split(r"[\s,]+|and\s+", raw_files) if t.strip()]

            steps = [
                DesktopStep(
                    step_id=1,
                    name=f"Create folder {folder_name}",
                    action_type=DesktopActionType.CREATE_FOLDER,
                    parameters={"folder_name": folder_name, "location": loc, "on_desktop": loc == "desktop"},
                ),
            ]
            if tokens and any("." in t for t in tokens):
                steps.append(
                    DesktopStep(
                        step_id=2,
                        name=f"Create files in {folder_name}",
                        action_type=DesktopActionType.CREATE_FILES,
                        parameters={"file_names": tokens, "parent_dir": folder_name, "location": loc},
                    )
                )
            elif tokens:
                for idx, sub in enumerate(tokens, start=2):
                    steps.append(
                        DesktopStep(
                            step_id=idx,
                            name=f"Create subfolder {sub}",
                            action_type=DesktopActionType.CREATE_FOLDER,
                            parameters={"folder_name": f"{folder_name}/{sub}", "location": loc},
                        )
                    )

            return DesktopTaskPlan(goal=f"Create {folder_name} project structure", steps=steps)

        # Case B: "Create a folder called MyProject on Desktop, create a.cpp inside it, then open it in VS Code"
        if "create" in lower and ("inside" in lower or "then open" in lower or "in vs code" in lower or "in vscode" in lower):
            steps = []
            m_folder = re.search(r"(?:folder|project)\s+(?:called|named)?\s*([a-zA-Z0-9_\-]+)", raw, re.IGNORECASE)
            folder_name = m_folder.group(1) if m_folder else "MyProject"
            loc = "desktop" if "desktop" in lower else "documents" if "documents" in lower else "downloads" if "downloads" in lower else "desktop"

            steps.append(
                DesktopStep(
                    step_id=1,
                    name=f"Create folder {folder_name}",
                    action_type=DesktopActionType.CREATE_FOLDER,
                    parameters={"folder_name": folder_name, "location": loc, "on_desktop": loc == "desktop"},
                )
            )

            # Check files
            m_file = re.search(r"create\s+([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)\s+inside", raw, re.IGNORECASE)
            if m_file:
                fname = m_file.group(1).strip()
                steps.append(
                    DesktopStep(
                        step_id=2,
                        name=f"Create {fname}",
                        action_type=DesktopActionType.CREATE_FILES,
                        parameters={"file_names": [fname], "parent_dir": folder_name, "location": loc},
                    )
                )
            elif "main.cpp" in lower or "a.cpp" in lower:
                fname = "a.cpp" if "a.cpp" in lower else "main.cpp"
                steps.append(
                    DesktopStep(
                        step_id=2,
                        name=f"Create {fname}",
                        action_type=DesktopActionType.CREATE_FILES,
                        parameters={"file_names": [fname], "parent_dir": folder_name, "location": loc},
                    )
                )

            if "vs code" in lower or "vscode" in lower:
                steps.append(
                    DesktopStep(
                        step_id=len(steps) + 1,
                        name="Open in VS Code",
                        action_type=DesktopActionType.OPEN_VS_CODE,
                        parameters={"app_name": "Visual Studio Code", "target_path": folder_name},
                    )
                )

            if len(steps) > 1:
                return DesktopTaskPlan(goal=f"Create project '{folder_name}' and setup files", steps=steps)

        return None
