import tempfile
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
import generate_assembly_guide as gen

COMMITTED = _paths.ROOT / "output" / "assembly-guide"


def listing(directory):
    """Output files, skipping only the .DS_Store Finder writes (git ignores it; any other file counts)."""
    return sorted(p.name for p in Path(directory).iterdir() if p.name != ".DS_Store")


class OutputDriftTest(unittest.TestCase):
    def test_dotfiles_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".DS_Store").write_bytes(b"x")
            (Path(tmp) / "step-01.svg").write_text("<svg/>")
            (Path(tmp) / ".stale.svg").write_text("<svg/>")
            self.assertEqual(listing(tmp), [".stale.svg", "step-01.svg"])  # only Finder's file is skipped

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
