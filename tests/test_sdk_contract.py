import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CrashpadSdkContractTest(unittest.TestCase):
    def stage_fake_macos_sdk(self, directory):
        root = Path(directory)
        source = root / "source"
        for name in ("client", "compat", "minidump", "snapshot", "util", "out/Release-arm64/gen"):
            (source / name).mkdir(parents=True)
        (source / "third_party/mini_chromium/mini_chromium").mkdir(parents=True)
        (source / "LICENSE").write_text("BSD", encoding="utf-8")
        (source / "out/Release-arm64/crashpad_handler").write_text("handler", encoding="utf-8")
        sdk = root / "sdk"
        env = os.environ | {
            "SDK_STAGE": str(sdk),
            "CRASHPAD_SRC": str(source),
            "SDK_OS": "macos",
            "SDK_ARCH": "arm64",
            "SDK_MINIMUM_SYSTEM_VERSION": "11.0",
        }
        subprocess.run(["scripts/stage-sdk.sh"], cwd=ROOT, env=env, check=True)
        return sdk

    def test_staged_manifest_uses_source_lock_and_unambiguous_target_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = self.stage_fake_macos_sdk(directory)
            subprocess.run(
                [
                    "python3", "scripts/validate-sdk-layout.py", str(sdk),
                    "--os", "macos", "--arch", "arm64",
                    "--minimum-system-version", "11.0",
                ],
                cwd=ROOT,
                check=True,
            )
            manifest = json.loads((sdk / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue((sdk / "bin/crashpad_handler").is_file())

        self.assertEqual(manifest["schemaVersion"], 2)
        self.assertEqual(manifest["os"], "macos")
        self.assertEqual(manifest["arch"], "arm64")
        self.assertEqual(manifest["minimumSystemVersion"], "11.0")
        self.assertNotIn("platform", manifest)
        source_lock = json.loads((ROOT / "config/source-lock.json").read_text(encoding="utf-8"))
        self.assertRegex(source_lock["crashpadRevision"], r"^[0-9a-f]{40}$")
        self.assertEqual(manifest["crashpadRevision"], source_lock["crashpadRevision"])

    def test_staging_requires_a_fresh_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            for name in ("client", "compat", "minidump", "snapshot", "util", "out/Release-arm64/gen"):
                (source / name).mkdir(parents=True)
            (source / "third_party/mini_chromium/mini_chromium").mkdir(parents=True)
            (source / "LICENSE").write_text("BSD", encoding="utf-8")
            (source / "out/Release-arm64/crashpad_handler").write_text("handler", encoding="utf-8")
            sdk = root / "sdk"
            sdk.mkdir()
            result = subprocess.run(
                ["scripts/stage-sdk.sh"],
                cwd=ROOT,
                env=os.environ | {
                    "SDK_STAGE": str(sdk),
                    "CRASHPAD_SRC": str(source),
                    "SDK_OS": "macos",
                    "SDK_ARCH": "arm64",
                    "SDK_MINIMUM_SYSTEM_VERSION": "11.0",
                },
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not exist", result.stderr)

    def test_cmake_version_file_accepts_the_sdk_version(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = self.stage_fake_macos_sdk(directory)
            project = Path(directory) / "consumer"
            project.mkdir()
            sdk_version = json.loads((ROOT / "config/sdk-version.json").read_text(encoding="utf-8"))["sdkVersion"]
            (project / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "project(crashpad_consumer NONE)\n"
                f"find_package(Crashpad {sdk_version} EXACT CONFIG REQUIRED)\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["cmake", "-S", str(project), "-B", str(Path(directory) / "build"), f"-DCrashpad_DIR={sdk / 'cmake'}"],
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cmake_version_file_rejects_a_different_version(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = self.stage_fake_macos_sdk(directory)
            project = Path(directory) / "consumer"
            project.mkdir()
            (project / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\n"
                "project(crashpad_consumer NONE)\n"
                "find_package(Crashpad 999.0 EXACT CONFIG REQUIRED)\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["cmake", "-S", str(project), "-B", str(Path(directory) / "build"), f"-DCrashpad_DIR={sdk / 'cmake'}"],
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)

    def test_workflow_uses_source_lock_and_matrix_target_variables(self):
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")

        self.assertIn("config/source-lock.json", workflow)
        self.assertIn("SDK_OS", workflow)
        self.assertIn("SDK_MINIMUM_SYSTEM_VERSION", workflow)
        pull_request = workflow.split("  pull_request:", 1)[1].split("permissions:", 1)[0]
        self.assertIn("'tests/**'", pull_request)
        self.assertNotIn("inputs.sdkVersion", workflow)

    def test_build_scripts_do_not_write_the_staged_sdk(self):
        for path in ("scripts/build-macos.sh", "scripts/build-windows.ps1"):
            content = (ROOT / path).read_text(encoding="utf-8")

            self.assertNotIn("SDK_STAGE", content)

        windows_builder = (ROOT / "scripts/build-windows.ps1").read_text(encoding="utf-8")
        self.assertNotIn("SDK_MINIMUM_SYSTEM_VERSION", windows_builder)

    def test_macos_builder_applies_the_iokit_compatibility_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "crashpad"
            source_file = source / "util/mac/mac_util.cc"
            source_file.parent.mkdir(parents=True)
            source_file.write_text(
                "\n" * 250
                + "void MacModelAndBoard(std::string* model, std::string* board_id) {\n"
                "  base::mac::ScopedIOObject<io_service_t> platform_expert(\n"
                "      IOServiceGetMatchingService(kIOMainPortDefault,\n"
                "                                  IOServiceMatching(\"IOPlatformExpertDevice\")));\n"
                "}\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(source), "add", "util/mac/mac_util.cc"], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-qm", "fixture"], check=True)
            tools = root / "tools"
            tools.mkdir()
            for tool in ("gn", "autoninja"):
                path = tools / tool
                path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
                path.chmod(0o755)
            result = subprocess.run(
                ["scripts/build-macos.sh"],
                cwd=ROOT,
                env=os.environ | {
                    "PATH": f"{tools}:{os.environ['PATH']}",
                    "RUNNER_TEMP": str(root),
                    "CRASHPAD_SRC": str(source),
                    "SDK_ARCH": "arm64",
                    "SDK_MINIMUM_SYSTEM_VERSION": "11.0",
                },
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("IOServiceGetMatchingService(MACH_PORT_NULL,", source_file.read_text(encoding="utf-8"))

    def test_platform_matrix_does_not_store_a_redundant_target_key(self):
        matrix = json.loads((ROOT / "config/platform-matrix.json").read_text(encoding="utf-8"))

        self.assertTrue(all("key" not in target for target in matrix["platforms"]))


if __name__ == "__main__":
    unittest.main()
