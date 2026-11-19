import tempfile
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
import generate_assembly_guide as gen

COMMITTED = _paths.ROOT / "output" / "assembly-guide"


def listing(directory):
    """Output files, ignoring dotfiles such as the .DS_Store Finder writes (git ignores them too)."""
    return sorted(p.name for p in Path(directory).iterdir() if not p.name.startswith("."))


class OutputDriftTest(unittest.TestCase):
    def test_dotfiles_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".DS_Store").write_bytes(b"x")
            (Path(tmp) / "step-01.svg").write_text("<svg/>")
            self.assertEqual(listing(tmp), ["step-01.svg"])

    def test_committed_output_matches(self):
        """The committed output/assembly-guide/ is what the generator writes now; regenerate on change."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "assembly-guide"
            gen.generate(out)
            fresh = listing(out)
            committed = listing(COMMITTED)
            self.assertEqual(fresh, committed)
            for name in fresh:
                self.assertEqual((out / name).read_bytes(), (COMMITTED / name).read_bytes(),
                                 f"{name} differs: run python3 MurphyBedQueen/generate_assembly_guide.py")


if __name__ == "__main__":
    unittest.main()
