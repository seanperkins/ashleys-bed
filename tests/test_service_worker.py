"""Runs the built sw.js fetch handler under node with stubbed caches and fetch."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
import build

HARNESS = r"""
const fs = require("fs");
const [swPath, mode] = process.argv.slice(2);
const listeners = {};
const store = new Map([["build-steps.html", "CACHED PAGE"]]);
const cache = {
  match: async (key) => (store.has(key) ? { ok: true, status: 200, body: store.get(key) } : undefined),
  put: async (key, value) => { store.set(key, value.body); },
  addAll: async () => {},
};
global.self = {
  registration: { scope: "https://example.test/site/" },
  location: { origin: "https://example.test" },
  addEventListener: (type, fn) => { listeners[type] = fn; },
  skipWaiting: () => {}, clients: { claim: () => {} },
};
global.caches = { open: async () => cache, keys: async () => [], delete: async () => true };
global.Request = class { constructor(url) { this.url = url; } };
global.fetch = async () => {
  if (mode === "offline") throw new TypeError("network down");
  if (mode === "error") return { ok: false, status: 503, body: "SERVER ERROR", clone() { return this; } };
  return { ok: true, status: 200, body: "FRESH PAGE", clone() { return this; } };
};
eval(fs.readFileSync(swPath, "utf8"));
let responded;
listeners.fetch({
  request: { method: "GET", url: "https://example.test/site/build-steps.html" },
  respondWith: (promise) => { responded = promise; },
});
responded.then((r) => console.log(JSON.stringify({ status: r.status, body: r.body })));
"""


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class ServiceWorkerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dest = Path(cls.tmp.name) / "_site"
        build.main(cls.dest)
        (Path(cls.tmp.name) / "harness.js").write_text(HARNESS)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, mode):
        out = subprocess.run(["node", str(Path(self.tmp.name) / "harness.js"), str(self.dest / "sw.js"), mode],
                             capture_output=True, text=True, timeout=20, check=True)
        return json.loads(out.stdout)

    def test_online_serves_network(self):
        self.assertEqual(self.page("online")["body"], "FRESH PAGE")

    def test_offline_serves_cache(self):
        self.assertEqual(self.page("offline")["body"], "CACHED PAGE")

    def test_server_error_serves_cache(self):
        self.assertEqual(self.page("error")["body"], "CACHED PAGE")


if __name__ == "__main__":
    unittest.main()
