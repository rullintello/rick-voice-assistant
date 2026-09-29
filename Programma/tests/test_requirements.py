"""requirements.txt: exact, tested versions on the Pythons Rick supports,
and nothing Rick imports left out of it."""

import ast
import sys
import unittest
from pathlib import Path

PROGRAMMA_DIR = Path(__file__).resolve().parent.parent
SUPPORTED = ["3.10", "3.11", "3.12", "3.13", "3.14"]

# import name -> the package that provides it
PACKAGE_OF = {
    "google": "google-genai",
    "tavily": "tavily-python",
    "keyboard": "keyboard",
    "sounddevice": "sounddevice",
    "soundfile": "soundfile",
    "numpy": "numpy",
    "miniaudio": "miniaudio",
    "dotenv": "python-dotenv",
    "faster_whisper": "faster-whisper",
    "edge_tts": "edge-tts",
}

try:
    from packaging.requirements import Requirement
except ImportError:  # pragma: no cover - comes with most Python installs
    Requirement = None


def _requirements(filename):
    lines = (PROGRAMMA_DIR / filename).read_text(encoding="utf-8").splitlines()
    return [Requirement(l) for l in lines if l.strip() and not l.lstrip().startswith("#")]


def _windows(python_version):
    return {
        "python_version": python_version, "python_full_version": python_version + ".0",
        "sys_platform": "win32", "platform_system": "Windows", "os_name": "nt",
        "implementation_name": "cpython", "platform_machine": "AMD64",
    }


@unittest.skipIf(Requirement is None, "the 'packaging' module isn't installed")
class RequirementsTest(unittest.TestCase):
    def active(self, filename, python_version):
        env = _windows(python_version)
        return [r for r in _requirements(filename) if r.marker is None or r.marker.evaluate(env)]

    def test_every_package_pinned_exactly_once_on_supported_pythons(self):
        for version in SUPPORTED:
            with self.subTest(python=version):
                active = self.active("requirements.txt", version)
                names = [r.name.lower() for r in active]
                self.assertEqual(len(names), len(set(names)), "a package is listed twice")
                loose = [str(r) for r in active if [s.operator for s in r.specifier] != ["=="]]
                self.assertEqual(loose, [])

    def test_newer_pythons_still_get_every_direct_dependency(self):
        active = {r.name for r in self.active("requirements.txt", "3.15")}
        self.assertEqual(active, set(PACKAGE_OF.values()))

    def test_everything_rick_imports_is_listed(self):
        listed = {r.name.lower() for r in _requirements("requirements.txt")}
        imported = set()
        for source in [*(PROGRAMMA_DIR / "rick").glob("*.py"), PROGRAMMA_DIR / "main.py", PROGRAMMA_DIR / "settings.py"]:
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    imported |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported.add(node.module.split(".")[0])
        third_party = imported - set(sys.stdlib_module_names) - {"rick"}
        unknown = third_party - PACKAGE_OF.keys()
        self.assertEqual(unknown, set(), "new import: add it to requirements.txt and PACKAGE_OF")
        missing = {PACKAGE_OF[m] for m in third_party} - listed
        self.assertEqual(missing, set())


if __name__ == "__main__":
    unittest.main()
