from pathlib import Path

from evolution.code_agent import EvolutionaryCodeAgent


class TestEvolutionaryCodeAgent:
    def setup_method(self, tmp_path=None):
        self.workspace = Path(str(tmp_path)) if tmp_path else Path(".")

    def test_stage_patch_creates_file(self, tmp_path):
        agent = EvolutionaryCodeAgent(workspace_root=str(tmp_path))
        patch_id = agent.stage_patch("src/lib.rs", "fn main() {}", "Refactor main")
        assert isinstance(patch_id, str)
        assert len(patch_id) == 12
        # Verify the patch file was created
        patches_dir = tmp_path / "evolution" / "patches"
        assert patches_dir.exists()
        patch_files = list(patches_dir.glob("patch_*.diff"))
        assert len(patch_files) == 1

    def test_patch_content_includes_metadata(self, tmp_path):
        agent = EvolutionaryCodeAgent(workspace_root=str(tmp_path))
        agent.stage_patch("src/lib.rs", "fn main() {}", "Refactor main")
        patch_file = next(iter((tmp_path / "evolution" / "patches").glob("patch_*.diff")))
        content = patch_file.read_text()
        assert "REASON: Refactor main" in content
        assert "TARGET: src/lib.rs" in content
        assert "fn main() {}" in content

    def test_patch_id_deterministic_for_same_content(self, tmp_path):
        agent = EvolutionaryCodeAgent(workspace_root=str(tmp_path))
        id1 = agent.stage_patch("f.rs", "code", "reason")
        id2 = agent.stage_patch("f.rs", "code", "reason")
        assert id1 == id2

    def test_patch_id_differs_for_different_content(self, tmp_path):
        agent = EvolutionaryCodeAgent(workspace_root=str(tmp_path))
        id1 = agent.stage_patch("f.rs", "code_a", "reason")
        id2 = agent.stage_patch("f.rs", "code_b", "reason")
        assert id1 != id2
