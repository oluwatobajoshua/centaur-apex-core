import hashlib
from pathlib import Path


class EvolutionaryCodeAgent:
    """
    Manages codebase entropy, identifies compiler or runtime obsolescence,
    and stages self-generated refactoring patches.
    """

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.patches_dir = self.workspace_root / "evolution" / "patches"

    def stage_patch(self, file_path: str, proposed_content: str, reason: str) -> str:
        patch_id = hashlib.sha256(proposed_content.encode("utf-8")).hexdigest()[:12]
        patch_filename = self.patches_dir / f"patch_{patch_id}.diff"

        metadata = f"# REASON: {reason}\n# TARGET: {file_path}\n\n"
        patch_filename.write_text(metadata + proposed_content, encoding="utf-8")

        print(f"Staged evolutionary patch [{patch_id}] for target: {file_path}")
        return patch_id
