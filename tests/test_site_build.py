import hashlib
import json
import re
import shutil
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from tests import _paths  # noqa: F401
import build

THREE = ["assets/vendor/three/build/three.module.min.js",
         "assets/vendor/three/examples/jsm/controls/OrbitControls.js",
         "assets/vendor/three/examples/jsm/loaders/GLTFLoader.js",
         "assets/vendor/three/examples/jsm/utils/BufferGeometryUtils.js"]


def snapshot(directory):
    return {str(p.relative_to(directory)): p.read_bytes() for p in sorted(directory.rglob("*")) if p.is_file()}


def precache(sw_text):
    return json.loads(re.search(r"const PRECACHE = (\[.*?\]);", sw_text, re.S).group(1))


class SiteBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dest = Path(cls.tmp.name) / "_site"
        cls.output_before = snapshot(build.OUT / "assembly-guide")
        build.main(cls.dest)
        cls.page = (cls.dest / "build-steps.html").read_text()
        cls.sw = (cls.dest / "sw.js").read_text()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_build_publishes_guide(self):
        guide = self.dest / "assembly-guide"
        self.assertTrue((guide / "assembly.glb").exists())
        steps = json.loads((guide / "assembly-steps.json").read_text())
        self.assertEqual(len(steps), 22)
        self.assertTrue((self.dest / "sw.js").exists())
        self.assertTrue((self.dest / "assets/assembly-viewer.js").exists())
        slugs = [p[0] for p in build.PAGES]
        self.assertEqual(slugs[slugs.index("assembly") + 1], "build-steps")


    def test_page_description(self):
        description = next(p[3] for p in build.PAGES if p[0] == "build-steps")
        self.assertEqual(description, "Interactive 3D steps for the bed cabinet and the bookcase; "
                                      "the bed mechanism steps follow.")

    def test_build_does_not_touch_output(self):
        self.assertEqual(snapshot(build.OUT / "assembly-guide"), self.output_before)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(build, "validate_site", side_effect=ValueError("forced")):
                with self.assertRaises(ValueError):
                    build.main(Path(tmp) / "_site")
        self.assertEqual(snapshot(build.OUT / "assembly-guide"), self.output_before)

    def test_validates_staged_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "_site"
            shutil.copytree(self.dest, dest)
            before = snapshot(dest)
            original = build.page_body
            broken = lambda slug: original(slug) + ('<a href="missing.html">x</a>' if slug == "index" else "")
            with mock.patch.object(build, "page_body", side_effect=broken):
                with self.assertRaisesRegex(ValueError, "missing.html"):
                    build.main(dest)
            self.assertEqual(snapshot(dest), before)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["_site"])

    def test_step_fragments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "build-steps.html").write_text("<p>guide</p>")
            (root / "a.html").write_text('<a href="build-steps.html#bookcase-drill">ok</a>')
            build.validate_site(root, {"build-steps.html": {"bookcase-drill"}})
            (root / "a.html").write_text('<a href="build-steps.html#nope">bad</a>')
            with self.assertRaisesRegex(ValueError, "#nope"):
                build.validate_site(root, {"build-steps.html": {"bookcase-drill"}})
        # the real build accepts deep links to both a bed and a bookcase step
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "_site"
            shutil.copytree(self.dest, dest)
            (dest / "deep.html").write_text('<a href="build-steps.html#bed-drill-sides">bed</a>'
                                            '<a href="build-steps.html#bookcase-drill">bookcase</a>')
            ids = {s["id"] for s in json.loads((dest / "assembly-guide/assembly-steps.json").read_text())}
            build.validate_site(dest, {"build-steps.html": ids})
            self.assertTrue({"bed-drill-sides", "bookcase-drill"} <= ids)

    def test_importmap_and_scripts(self):
        imports = json.loads(re.search(r'<script type="importmap">(.*?)</script>', self.page, re.S).group(1))
        self.assertEqual(imports["imports"]["three"], "./assets/vendor/three/build/three.module.min.js")
        self.assertIn('<script type="module" src="assets/assembly-viewer.js"></script>', self.page)
        self.assertLess(self.page.index("importmap"), self.page.index("assembly-viewer.js"))
        for path in THREE:
            self.assertTrue((self.dest / path).exists(), path)

    def test_sw_precache(self):
        files = precache(self.sw)
        for path in ["build-steps.html", "assets/style.css", "assets/guide.js", "assets/favicon.svg",
                     "assets/assembly-viewer.js", *THREE, "assembly-guide/assembly.glb",
                     "assembly-guide/assembly-steps.json"]:
            self.assertIn(path, files)
        svgs = sorted(p.name for p in (self.dest / "assembly-guide").glob("*.svg"))
        self.assertEqual(sorted(f.split("/")[-1] for f in files if f.endswith(".svg") and "favicon" not in f), svgs)
        digest = hashlib.sha256()
        for path in files:
            digest.update((self.dest / path).read_bytes())
        self.assertIn(f'const CACHE = "guide-{digest.hexdigest()[:16]}";', self.sw)
        self.assertIn('key.startsWith("guide-") && key !== CACHE', self.sw)

    def test_sw_hash_tracks_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "_site"
            shutil.copytree(self.dest, dest)
            first = build.render_sw(dest)
            (dest / "assets/style.css").write_text("/* changed */", encoding="utf-8")
            self.assertNotEqual(build.render_sw(dest), first)

    def test_leftover_tmp_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "_site.tmp-old").mkdir()
            (Path(tmp) / "_site.backup-old").mkdir()
            build.main(Path(tmp) / "_site")
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["_site"])

    def test_guide_noscript(self):
        noscript = re.search(r"<noscript>(.*?)</noscript>", self.page, re.S).group(1)
        self.assertNotIn("work without JavaScript", noscript)
        self.assertIn("need JavaScript", noscript)
        for i in range(1, 23):
            self.assertIn(f'href="assembly-guide/step-{i:02d}.svg"', noscript)
        for path in (self.dest / "assembly-guide").glob("*-holes.svg"):
            self.assertIn(f'href="assembly-guide/{path.name}"', noscript)
        self.assertEqual(len(list((self.dest / "assembly-guide").glob("*-holes.svg"))), 14)
        other = (self.dest / "assembly.html").read_text()
        self.assertIn("All instructions and downloads work without JavaScript", other)

    def test_guide_footer(self):
        footer = re.search(r"<footer>(.*?)</footer>", self.page, re.S).group(1)
        self.assertIn("drawn from the Rockler manual and this project’s design", footer)
        self.assertNotIn("Bed steps name", footer)
        self.assertNotIn("Use this guide alongside", footer)
        self.assertIn("Use this guide alongside", (self.dest / "index.html").read_text())

    def test_guide_has_no_cnc_release_bar(self):
        self.assertNotIn("release-bar", self.page)
        self.assertIn("release-bar", (self.dest / "cnc.html").read_text())

    def test_published_dirs_readable(self):
        import stat
        for path in (self.dest, self.dest / "assembly-guide"):
            mode = path.stat().st_mode
            self.assertTrue(mode & stat.S_IROTH and mode & stat.S_IXOTH, oct(mode))

    def test_guide_page_links_resolve(self):
        self.assertIn('href="build-steps.html"', (self.dest / "assembly.html").read_text())


    def test_viewer_poses_hardware(self):
        viewer = (self.dest / "assets/assembly-viewer.js").read_text()
        self.assertIn("item.axes", viewer)  # per-node axes when one item's nodes face different ways
        self.assertNotRegex(viewer, r"hardwareStep\.has\(name\)\) \{\s*object\.visible = [^;]+;\s*object\.matrix\.identity\(\)")


if __name__ == "__main__":
    unittest.main()
