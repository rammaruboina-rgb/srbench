"""srbench: tools for authoring, verifying and diagnosing search-resistant benchmark tasks."""
from .diagnose import Diagnosis, diagnose
from .gates import TaskVerdict, check_task
from .grader import Grade, grade
from .lint import lint_prompt
from .schema import Answer, Run, Source, Step, Task, load_runs, load_tasks

__version__ = "0.2.0"
__all__ = ["Answer", "Diagnosis", "Grade", "Run", "Source", "Step", "Task", "TaskVerdict",
           "check_task", "diagnose", "grade", "lint_prompt", "load_runs", "load_tasks"]
