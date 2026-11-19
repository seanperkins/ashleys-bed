import tempfile
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
import generate_assembly_guide as gen

COMMITTED = _paths.ROOT / "output" / "assembly-guide"


class OutputDriftTest(unittest.TestCase):
    def test_committed_output_matches(self):
        """The committed output/assembly-guide/ is what the generator writes now; regenerate on change."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "assembly-guide"
            gen.generate(out)
            fresh = sorted(p.name for p in out.iterdir())
            committed = sorted(p.name for p in COMMITTED.iterdir())
            self.assertEqual(fresh, committed)
            for name in fresh:
                self.assertEqual((out / name).read_bytes(), (COMMITTED / name).read_bytes(),
                                 f"{name} differs: run python3 MurphyBedQueen/generate_assembly_guide.py")


if __name__ == "__main__":
    unittest.main()
