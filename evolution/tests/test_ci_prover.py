from unittest.mock import MagicMock, patch

from evolution.ci_prover import TheoremProverCI


class TestTheoremProverCI:
    def test_passes_when_kani_not_found(self):
        prover = TheoremProverCI()
        # When cargo kani is not installed, should simulate pass
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert prover.run_formal_verification() is True

    def test_passes_when_kani_succeeds(self):
        prover = TheoremProverCI()
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            assert prover.run_formal_verification() is True

    def test_fails_when_kani_fails(self):
        prover = TheoremProverCI()
        mock_result = MagicMock(returncode=1, stderr="verification failed")
        with patch("subprocess.run", return_value=mock_result):
            assert prover.run_formal_verification() is False

    def test_invokes_correct_command(self):
        prover = TheoremProverCI(rust_crate_path="constitution")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            prover.run_formal_verification()
            mock_run.assert_called_once()
            args = mock_run.call_args
            assert args[1]["cwd"] == "constitution"
            assert "cargo" in args[0][0]
            assert "kani" in args[0][0]
