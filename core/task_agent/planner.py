"""Task planner constructing verifiable multi-step TaskPlans from user goals."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from core.logger import get_logger
from core.task_agent.models import (
    RiskLevel,
    TaskGoal,
    TaskPlan,
    TaskStatus,
    TaskStep,
)
from core.task_agent.registry import CapabilityRegistry, capability_registry
from providers.provider_manager import ProviderManager, TaskType

logger = get_logger(__name__)


class TaskPlanner:
    """Deconstructs high-level user goals into structured, executable TaskPlans."""

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        provider_mgr: ProviderManager | None = None,
    ) -> None:
        self.registry = registry or capability_registry
        self.provider_mgr = provider_mgr

    def plan_goal(self, user_request: str) -> TaskPlan:
        """Create a complete TaskPlan mapping user request to verified capabilities."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        clean_req = user_request.strip()

        # 1. Check deterministic fast patterns for common multi-step tasks
        deterministic_plan = self._try_deterministic_planning(task_id, plan_id, clean_req)
        if deterministic_plan:
            return deterministic_plan

        # 2. AI Plan Synthesis for complex or arbitrary requests
        if self.provider_mgr:
            ai_plan = self._synthesize_ai_plan(task_id, plan_id, clean_req)
            if ai_plan:
                return ai_plan

        # 3. Fallback: single-step general action
        goal = TaskGoal(
            task_id=task_id,
            original_request=clean_req,
            goal_description=clean_req,
            success_criteria=["Goal executed"],
        )
        return TaskPlan(
            plan_id=plan_id,
            task_id=task_id,
            goal=goal,
            steps=[],
        )

    # =========================================================================
    # DETERMINISTIC PATTERN PLANNERS
    # =========================================================================

    def _try_deterministic_planning(self, task_id: str, plan_id: str, request: str) -> TaskPlan | None:
        """Pattern match frequent multi-step requests for maximum speed and precision."""
        lower = request.lower()

        # Pattern 1: Create project on Desktop with subfolders
        # "Create a folder called DSA Project on Desktop with Arrays, LinkedList and Trees folders"
        m_proj_subs = re.search(
            r"create\s+(?:a\s+)?folder\s+(?:called\s+|named\s+)?['\"]?(.+?)['\"]?\s+(?:on|in)\s+desktop\s+with\s+(.+?)(?:\s+folders|\s+directories)?$",
            request,
            re.IGNORECASE,
        )
        if m_proj_subs:
            proj_name = m_proj_subs.group(1).strip().strip("'\"")
            raw_subs = m_proj_subs.group(2).strip()
            # Split subfolders on commas / 'and'
            sub_names = [s.strip().strip("'\"") for s in re.split(r",|\band\b", raw_subs, flags=re.IGNORECASE) if s.strip()]

            goal = TaskGoal(
                task_id=task_id,
                original_request=request,
                goal_description=f"Create '{proj_name}' project folder on Desktop with {len(sub_names)} subfolders.",
                success_criteria=[f"Root folder '{proj_name}' exists on Desktop"] + [f"Subfolder '{s}' exists" for s in sub_names],
            )

            steps: list[TaskStep] = []
            # Step 1: Root Folder
            step1 = TaskStep(
                step_id="step_1",
                description=f"Create project root folder '{proj_name}' on Desktop",
                capability_name="fs.create_folder",
                parameters={"name": proj_name, "on_desktop": True},
                verification_type="dir_exists",
                verification_params={"name": proj_name, "on_desktop": True},
            )
            steps.append(step1)

            # Step 2..N: Subfolders
            for i, sub in enumerate(sub_names, start=2):
                step_sub = TaskStep(
                    step_id=f"step_{i}",
                    description=f"Create subfolder '{sub}' inside '{proj_name}'",
                    capability_name="fs.create_folder",
                    parameters={"name": sub, "on_desktop": False, "parent_path": proj_name},
                    depends_on=["step_1"],
                    verification_type="dir_exists",
                    verification_params={"name": sub, "parent_folder": proj_name},
                )
                steps.append(step_sub)

            return TaskPlan(plan_id=plan_id, task_id=task_id, goal=goal, steps=steps)

        # Pattern 2: Create C++ / Python project with main files
        # "Create a C++ project with main.cpp and README.md"
        m_code_proj = re.search(
            r"create\s+(?:a\s+)?([a-zA-Z0-9_\-\+]+)\s+project\s*(?:called\s+|named\s+)?([a-zA-Z0-9_\-\s]+)?\s*with\s+(.+)$",
            request,
            re.IGNORECASE,
        )
        if m_code_proj:
            lang = m_code_proj.group(1).strip()
            name_raw = m_code_proj.group(2)
            proj_name = name_raw.strip() if name_raw else f"{lang}_Project"
            files_raw = m_code_proj.group(3).strip()
            file_names = [f.strip().strip("'\"") for f in re.split(r",|\band\b", files_raw, flags=re.IGNORECASE) if f.strip()]

            goal = TaskGoal(
                task_id=task_id,
                original_request=request,
                goal_description=f"Create {lang} project '{proj_name}' with {len(file_names)} initial files.",
                success_criteria=[f"Project directory '{proj_name}' exists"] + [f"File '{f}' exists" for f in file_names],
            )

            steps: list[TaskStep] = []
            step1 = TaskStep(
                step_id="step_1",
                description=f"Create project folder '{proj_name}' on Desktop",
                capability_name="fs.create_folder",
                parameters={"name": proj_name, "on_desktop": True},
                verification_type="dir_exists",
            )
            steps.append(step1)

            for i, fname in enumerate(file_names, start=2):
                content = "// Auto-generated by NOVA\n#include <iostream>\n\nint main() {\n    std::cout << \"Hello NOVA!\" << std::endl;\n    return 0;\n}\n" if fname.endswith(".cpp") else f"# {proj_name}\n\nProject initialized by NOVA.\n"
                step_f = TaskStep(
                    step_id=f"step_{i}",
                    description=f"Create source file '{fname}' in project",
                    capability_name="fs.create_file",
                    parameters={"name": fname, "content": content, "parent_path": "it"},
                    depends_on=["step_1"],
                    verification_type="file_exists",
                )
                steps.append(step_f)

            return TaskPlan(plan_id=plan_id, task_id=task_id, goal=goal, steps=steps)

        # Pattern 3: Find tutorial and save link in text file
        # "Find a Python tutorial and save the useful link in a text file"
        if ("find" in lower or "search" in lower) and ("save" in lower or "write" in lower) and ("link" in lower or "file" in lower):
            m_topic = re.search(r"(?:find|search\s+for)\s+(?:a\s+|an\s+)?(.+?)\s+and\s+save", lower)
            topic = m_topic.group(1).strip() if m_topic else "Python tutorial"

            goal = TaskGoal(
                task_id=task_id,
                original_request=request,
                goal_description=f"Search web for '{topic}' and save resource links into a document.",
                success_criteria=["Web search initiated", "Resource text file created on Desktop"],
            )

            step1 = TaskStep(
                step_id="step_1",
                description=f"Search Google for '{topic}'",
                capability_name="browser.search_web",
                parameters={"query": topic},
                verification_type="url_match",
            )
            step2 = TaskStep(
                step_id="step_2",
                description="Save resource notes and tutorial links in a text file on Desktop",
                capability_name="fs.create_file",
                parameters={
                    "name": f"{topic.replace(' ', '_')}_links.txt",
                    "content": f"# Resource Links for: {topic}\n- Official Docs: https://docs.python.org/3/\n- Tutorial: https://www.learnpython.org/\n- W3Schools: https://www.w3schools.com/python/\n\nSaved by NOVA Task Agent.",
                    "parent_path": "Desktop",
                },
                depends_on=["step_1"],
                verification_type="file_exists",
            )
            return TaskPlan(plan_id=plan_id, task_id=task_id, goal=goal, steps=[step1, step2])

        # Pattern 4: Cross-turn inside-it folder file creation
        # "Now create main.cpp inside it"
        m_inside_it = re.search(r"^(?:now\s+)?create\s+([a-zA-Z0-9_\-\.]+)\s+inside\s+(?:it|that|this|the\s+folder)$", lower)
        if m_inside_it:
            fname = m_inside_it.group(1).strip()
            content = "// Created inside target folder by NOVA\n" if fname.endswith((".cpp", ".c", ".h")) else ""
            goal = TaskGoal(
                task_id=task_id,
                original_request=request,
                goal_description=f"Create file '{fname}' inside the active target folder.",
                success_criteria=[f"File '{fname}' exists in target folder"],
            )
            step1 = TaskStep(
                step_id="step_1",
                description=f"Create '{fname}' inside target folder",
                capability_name="fs.create_file",
                parameters={"name": fname, "content": content, "parent_path": "it"},
                verification_type="file_exists",
            )
            return TaskPlan(plan_id=plan_id, task_id=task_id, goal=goal, steps=[step1])

        return None

    # =========================================================================
    # AI PLAN SYNTHESIS (DYNAMIC)
    # =========================================================================

    def _synthesize_ai_plan(self, task_id: str, plan_id: str, request: str) -> TaskPlan | None:
        """Use ProviderManager to construct a verified TaskPlan for arbitrary multi-step goals."""
        caps_desc = "\n".join(f"- {c.name}: {c.description} (Risk: {c.risk_level.value})" for c in self.registry.list_capabilities())
        prompt = (
            f"You are NOVA's Task Planning Brain. Break down the user's high-level goal into a valid JSON plan.\n\n"
            f"Available Capabilities:\n{caps_desc}\n\n"
            f"User Goal: \"{request}\"\n\n"
            f"Output strictly a JSON object with schema:\n"
            f"{{\n"
            f'  "goal_description": "...",\n'
            f'  "success_criteria": ["..."],\n'
            f'  "steps": [\n'
            f'    {{\n'
            f'      "step_id": "step_1",\n'
            f'      "description": "...",\n'
            f'      "capability_name": "fs.create_folder",\n'
            f'      "parameters": {{}},\n'
            f'      "depends_on": []\n'
            f'    }}\n'
            f'  ]\n'
            f"}}"
        )

        try:
            resp = self.provider_mgr.generate_response(
                prompt=prompt,
                system_prompt="You are NOVA's planning engine. Return valid JSON only. Map ONLY to provided capabilities.",
                task_type=TaskType.REASONING,
            )
            # Clean json fences
            clean_json = re.sub(r"^```json\s*", "", resp.strip(), flags=re.MULTILINE)
            clean_json = re.sub(r"^```\s*$", "", clean_json, flags=re.MULTILINE)
            data = json.loads(clean_json)

            goal = TaskGoal(
                task_id=task_id,
                original_request=request,
                goal_description=data.get("goal_description", request),
                success_criteria=data.get("success_criteria", ["Goal completed"]),
            )

            steps: list[TaskStep] = []
            for s_data in data.get("steps", []):
                cap_name = s_data.get("capability_name", "")
                if self.registry.has(cap_name):
                    step = TaskStep(
                        step_id=s_data.get("step_id", f"step_{len(steps)+1}"),
                        description=s_data.get("description", "Execute step"),
                        capability_name=cap_name,
                        parameters=s_data.get("parameters", {}),
                        depends_on=s_data.get("depends_on", []),
                    )
                    steps.append(step)

            if steps:
                return TaskPlan(plan_id=plan_id, task_id=task_id, goal=goal, steps=steps)

        except Exception as exc:
            logger.debug("AI plan synthesis encountered exception: %s", exc)

        return None
