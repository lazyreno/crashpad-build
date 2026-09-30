import json
import os
import subprocess
import sys
import tempfile
import unittest
import hashlib
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
        # GN prefixes static libraries with "lib" on macOS.
        (source / "out/Release-arm64/obj/client").mkdir(parents=True)
        (source / "out/Release-arm64/obj/client/libclient.a").write_bytes(b"client archive")
        (source / "out/Release-arm64/obj/client/libcommon.a").write_bytes(
            b"CrashReportDatabase::InitializeWithoutCreating"
        )
        sdk = root / "sdk"
        env = os.environ | {
            "SDK_STAGE": str(sdk),
            "CRASHPAD_SRC": str(source),
            "SDK_OS": "macos",
            "SDK_ARCH": "arm64",
            "SDK_CONFIGURATION": "release",
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
                    "--configuration", "release",
                    "--minimum-system-version", "11.0",
                ],
                cwd=ROOT,
                check=True,
            )
            manifest = json.loads((sdk / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue((sdk / "bin/crashpad_handler").is_file())

        self.assertEqual(manifest["schemaVersion"], 3)
        self.assertEqual(manifest["os"], "macos")
        self.assertEqual(manifest["arch"], "arm64")
        self.assertEqual(manifest["configuration"], "release")
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
                    "SDK_CONFIGURATION": "release",
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

    def test_release_tags_run_the_full_upstream_test_suite(self):
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        macos_builder = (ROOT / "scripts/build-macos.sh").read_text(encoding="utf-8")
        windows_builder = (ROOT / "scripts/build-windows.ps1").read_text(encoding="utf-8")

        self.assertIn("CRASHPAD_RUN_UPSTREAM_TESTS: ${{ startsWith(github.ref, 'refs/tags/v') }}", workflow)
        publish_release = workflow.split("  publish-release:", 1)[1]
        self.assertIn("if: startsWith(github.ref, 'refs/tags/v')", publish_release)
        self.assertNotIn("workflow_dispatch", publish_release)
        for target in (
            "crashpad_client_test",
            "crashpad_handler_test",
            "crashpad_minidump_test",
            "crashpad_snapshot_test",
            "crashpad_test_test",
            "crashpad_util_test",
        ):
            self.assertIn(target, macos_builder)
            self.assertIn(target, windows_builder)
        self.assertIn('CRASHPAD_RUN_UPSTREAM_TESTS:-false', macos_builder)
        self.assertIn("CRASHPAD_RUN_UPSTREAM_TESTS -eq 'true'", windows_builder)

    def test_release_test_environment_uses_native_runners_and_known_workarounds(self):
        matrix = json.loads((ROOT / "config/platform-matrix.json").read_text(encoding="utf-8"))
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        macos_builder = (ROOT / "scripts/build-macos.sh").read_text(encoding="utf-8")
        windows_builder = (ROOT / "scripts/build-windows.ps1").read_text(encoding="utf-8")
        runners = {(target["os"], target["arch"]): target["runner"] for target in matrix["platforms"]}

        self.assertEqual(runners[("macos", "x64")], "macos-15-intel")
        self.assertEqual(runners[("windows", "arm64")], "windows-11-vs2026-arm")
        self.assertIn("for attempt in 1 2 3; do", workflow)
        self.assertIn("--gtest_filter=-ExcClientVariants.UniversalExceptionRaise", macos_builder)
        self.assertNotIn('SDK_ARCH" == "arm64"', macos_builder)
        self.assertIn("tzutil /s 'Pacific Standard Time'", windows_builder)

    def test_arm64_workflow_verifies_the_native_msvc_producer(self):
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")

        self.assertIn("Verify native ARM64 MSVC toolchain", workflow)
        self.assertIn("matrix.arch == 'arm64'", workflow)
        self.assertIn("PROCESSOR_ARCHITECTURE", workflow)
        self.assertIn("14.44.35207", workflow)
        self.assertIn("HostARM64\\ARM64\\cl.exe", workflow)
        self.assertNotIn("& $compiler /Bv", workflow)

    def test_build_scripts_do_not_write_the_staged_sdk(self):
        for path in ("scripts/build-macos.sh", "scripts/build-windows.ps1"):
            content = (ROOT / path).read_text(encoding="utf-8")

            self.assertNotIn("SDK_STAGE", content)

        windows_builder = (ROOT / "scripts/build-windows.ps1").read_text(encoding="utf-8")
        self.assertNotIn("SDK_MINIMUM_SYSTEM_VERSION", windows_builder)

    def run_windows_builder(self, configuration):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "crashpad"
            tools = root / "tools"
            arguments = root / "gn-arguments.txt"
            source.mkdir()
            tools.mkdir()
            if os.name == "nt":
                (tools / "gn.cmd").write_text(
                    "@echo off\r\n"
                    "echo %* > \"%CRASHPAD_GN_ARGUMENTS_FILE%\"\r\n",
                    encoding="utf-8",
                )
                (tools / "autoninja.cmd").write_text(
                    "@echo off\r\n"
                    "echo %* >> \"%CRASHPAD_GN_ARGUMENTS_FILE%\"\r\n",
                    encoding="utf-8",
                )
            else:
                (tools / "gn").write_text(
                    "#!/usr/bin/env bash\n"
                    "printf '%s\\n' \"$@\" > \"$CRASHPAD_GN_ARGUMENTS_FILE\"\n",
                    encoding="utf-8",
                )
                (tools / "autoninja").write_text(
                    "#!/usr/bin/env bash\n"
                    "printf '%s\\n' \"$@\" >> \"$CRASHPAD_GN_ARGUMENTS_FILE\"\n",
                    encoding="utf-8",
                )
                for tool in (tools / "gn", tools / "autoninja"):
                    tool.chmod(0o755)

            result = subprocess.run(
                ["pwsh", "-NoProfile", "-File", "scripts/build-windows.ps1"],
                cwd=ROOT,
                env=os.environ | {
                    "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
                    "CRASHPAD_SRC": str(source),
                    "SDK_ARCH": "x64",
                    "SDK_CONFIGURATION": configuration,
                    "CRASHPAD_GN_ARGUMENTS_FILE": str(arguments),
                },
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            return arguments.read_text(encoding="utf-8")

    def test_windows_release_builder_requests_the_dynamic_release_crt(self):
        arguments = self.run_windows_builder("release")

        self.assertIn('out/Release-x64', arguments)
        self.assertIn('is_debug=false', arguments)
        self.assertIn('extra_cflags="/MD"', arguments)

    def test_windows_debug_builder_requests_the_dynamic_debug_crt(self):
        arguments = self.run_windows_builder("debug")

        self.assertIn('out/Debug-x64', arguments)
        self.assertIn('is_debug=true', arguments)
        self.assertIn('extra_cflags="/MDd"', arguments)

    def test_windows_arm64_builder_pins_the_native_msvc_toolset(self):
        windows_builder = (ROOT / "scripts/build-windows.ps1").read_text(encoding="utf-8")

        self.assertIn("-host_arch=arm64", windows_builder)
        self.assertIn("-arch=arm64", windows_builder)
        self.assertIn("$toolsetVersion = '14.44.35207'", windows_builder)
        self.assertIn("-vcvars_ver=$toolsetVersion", windows_builder)
        self.assertIn("HostARM64\\ARM64\\cl.exe", windows_builder)
        self.assertIn('is_clang=false', windows_builder)

    def test_windows_builder_builds_the_client_and_database_archives_for_sdk_consumers(self):
        """The staged SDK must expose Crashpad client database APIs, not only the handler."""
        arguments = self.run_windows_builder("debug")

        self.assertIn("crashpad_handler", arguments)
        self.assertIn("client", arguments)
        self.assertIn("client:common", arguments)

    def test_windows_staging_keeps_configurations_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            for name in ("client", "compat", "minidump", "snapshot", "util"):
                (source / name).mkdir(parents=True)
            (source / "third_party/mini_chromium/mini_chromium").mkdir(parents=True)
            (source / "LICENSE").write_text("BSD", encoding="utf-8")
            for configuration, output in (("release", "Release-x64"), ("debug", "Debug-x64")):
                build = source / "out" / output
                (build / "gen").mkdir(parents=True)
                (build / "crashpad_handler.exe").write_text(configuration, encoding="utf-8")
                (build / f"{configuration}.lib").write_text(configuration, encoding="utf-8")
                (build / "obj/client").mkdir(parents=True)
                (build / "obj/client/client.lib").write_text("client", encoding="utf-8")
                (build / "obj/client/common.lib").write_text("common", encoding="utf-8")
                sdk = root / configuration
                subprocess.run(
                    ["scripts/stage-sdk.sh"],
                    cwd=ROOT,
                    env=os.environ | {
                        "SDK_STAGE": str(sdk),
                        "CRASHPAD_SRC": str(source),
                        "SDK_OS": "windows",
                        "SDK_ARCH": "x64",
                        "SDK_CONFIGURATION": configuration,
                        "SDK_MINIMUM_SYSTEM_VERSION": "10.0",
                    },
                    check=True,
                )
                self.assertTrue((sdk / "lib" / f"{configuration}.lib").is_file())
                other = "debug" if configuration == "release" else "release"
                self.assertFalse((sdk / "lib" / f"{other}.lib").exists())
                manifest = json.loads((sdk / "manifest.json").read_text(encoding="utf-8"))
                self.assertIn("configuration", manifest)
                self.assertEqual(manifest["configuration"], configuration)

    def test_windows_staging_requires_the_crashpad_database_library(self):
        """Reject an SDK that can start the handler but cannot enumerate reports."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            for name in ("client", "compat", "minidump", "snapshot", "util"):
                (source / name).mkdir(parents=True)
            (source / "third_party/mini_chromium/mini_chromium").mkdir(parents=True)
            (source / "LICENSE").write_text("BSD", encoding="utf-8")
            build = source / "out" / "Debug-x64"
            (build / "gen").mkdir(parents=True)
            (build / "crashpad_handler.exe").write_text("handler", encoding="utf-8")
            (build / "obj/client").mkdir(parents=True)
            (build / "obj/client/client.lib").write_text("client", encoding="utf-8")
            tools = root / "tools"
            tools.mkdir()
            python3 = tools / "python3"
            python3.write_text(
                "#!/usr/bin/env bash\n"
                "exec \"$CRASHPAD_TEST_PYTHON\" \"$@\"\n",
                encoding="utf-8",
            )
            python3.chmod(0o755)

            stage_command = ["scripts/stage-sdk.sh"]
            sdk_stage = str(root / "sdk")
            crashpad_source = str(source)
            tool_path = str(tools)
            if os.name == "nt":
                bash = r"C:\Program Files\Git\bin\bash.exe"
                stage_command.insert(0, bash)

                def as_bash_path(path):
                    return subprocess.run(
                        [bash, "-lc", 'cygpath -u "$1"', "bash", path],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        check=True,
                    ).stdout.strip()

                sdk_stage = as_bash_path(sdk_stage)
                crashpad_source = as_bash_path(crashpad_source)
                tool_path = as_bash_path(tool_path)
            result = subprocess.run(
                stage_command,
                cwd=ROOT,
                env=os.environ | {
                    "SDK_STAGE": sdk_stage,
                    "CRASHPAD_SRC": crashpad_source,
                    "SDK_OS": "windows",
                    "SDK_ARCH": "x64",
                    "SDK_CONFIGURATION": "debug",
                    "SDK_MINIMUM_SYSTEM_VERSION": "10.0",
                    "CRASHPAD_TEST_PYTHON": sys.executable,
                    "PATH": tool_path + ":/usr/bin:/bin",
                },
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Crashpad database library is missing", result.stderr)

    def test_sdk_validation_rejects_a_database_library_without_database_open_api(self):
        """The staged database archive must export the API consumed by desktop-base."""
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory) / "sdk"
            (sdk / "lib").mkdir(parents=True)
            (sdk / "lib" / "obj/client").mkdir(parents=True)
            (sdk / "lib" / "obj/client/common.lib").write_bytes(
                b"Crashpad common archive without database API"
            )
            result = subprocess.run(
                [sys.executable, "scripts/validate-client-database-symbol.py", str(sdk)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("InitializeWithoutCreating", result.stderr)

    def test_staging_preserves_library_subdirectories_to_prevent_name_collisions(self):
        stage_script = (ROOT / "scripts/stage-sdk.sh").read_text(encoding="utf-8")
        cmake_targets = (ROOT / "scripts/stage-sdk.sh").read_text(encoding="utf-8")

        self.assertIn('relative_library="${library#"$build_dir"/}"', stage_script)
        self.assertIn('destination="$SDK_STAGE/lib/$relative_library"', stage_script)
        self.assertIn('file(GLOB_RECURSE _crashpad_libs', cmake_targets)

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
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("IOServiceGetMatchingService(MACH_PORT_NULL,", source_file.read_text(encoding="utf-8"))

    def test_artifact_index_uses_the_requested_base_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "release"
            assets.mkdir()
            expected_targets = (
                ("macos", "arm64", "release"),
                ("macos", "x64", "release"),
                ("windows", "arm64", "release"),
                ("windows", "arm64", "debug"),
                ("windows", "x64", "release"),
                ("windows", "x64", "debug"),
            )
            for os_name, arch, configuration in expected_targets:
                name = f"crashpad-sdk-{os_name}-{arch}-{configuration}.zip"
                archive = assets / name
                archive.write_bytes(name.encode("utf-8"))
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                (assets / f"{name}.sha256").write_text(f"{digest}  {name}\n", encoding="utf-8")
            output = root / "artifact-index.json"
            result = subprocess.run(
                [
                    "python3", "scripts/generate-artifact-index.py",
                    "--release-assets", str(assets),
                    "--output", str(output),
                    "--base-url", "https://example.invalid/releases/v20260929.1",
                    "--release-tag", "v20260929.1",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            index = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(index["releaseTag"], "v20260929.1")
            self.assertEqual(
                index["artifacts"][0]["url"],
                "https://example.invalid/releases/v20260929.1/crashpad-sdk-macos-arm64-release.zip",
            )
            self.assertEqual(index["artifacts"][0]["configuration"], "release")

    def test_platform_matrix_lists_configuration_qualified_targets(self):
        matrix = json.loads((ROOT / "config/platform-matrix.json").read_text(encoding="utf-8"))

        self.assertTrue(all("key" not in target for target in matrix["platforms"]))
        self.assertTrue(all("configuration" in target for target in matrix["platforms"]))
        self.assertEqual(
            {(target["os"], target["arch"], target["configuration"])
             for target in matrix["platforms"]},
            {
                ("macos", "arm64", "release"),
                ("macos", "x64", "release"),
                ("windows", "arm64", "release"),
                ("windows", "arm64", "debug"),
                ("windows", "x64", "release"),
                ("windows", "x64", "debug"),
            },
        )


if __name__ == "__main__":
    unittest.main()
