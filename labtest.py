import zipfile
import shutil
import os
import stat
import glob
import subprocess
import shlex
import time
import re
import sys
import uuid
import getpass
import argparse
import atexit
import urllib.request
from pathlib import Path

TESTER_DIR = ".labtest"
PROJECT_EXECUTABLE_PATH = os.path.join(TESTER_DIR, "project.out")
EXAMPLE_IO_PATH = os.path.join(TESTER_DIR, "exampleio")
PASS_OFF_CASES_PATH = os.path.join(TESTER_DIR, "passoff")
OUTPUT_ZIP_FILE_NAME = "project{:d}.zip"
TESTS_ZIP_URL = "https://students.cs.byu.edu/~th443/cs236_files/{:s}"
EXAMPLE_IO_ZIP_FILE_NAME = "project{:d}-exampleIO.zip"
PASS_OFF_CASES_ZIP_FILE_NAME = "Lab{:d}PassOffCases.zip"
PUBLIC_HTML_PATH = os.path.join(Path.home(), "public_html")
SCHIZO_LINK_PASSOFFS_PATH = os.path.join(PUBLIC_HTML_PATH, "labtest-passoffs")
DEFAULT_TEST_SUITE_TIME_LIMIT_S = 60

# Change this as suits your setup
CPU_CORES = 4


class CompileFailedError(Exception):
    pass


class CompileSetupFailedError(Exception):
    pass


class ExecuteError(Exception):
    pass


class TestsFailedError(Exception):
    pass


def color_wrap(input_str, color):
    return f"\033[1;{color};40m{input_str}\033[0m"


def compile_gxx():
    compile_process = subprocess.run(
        f"g++ -Wall -Werror -std=c++17 -g *.cpp -o {PROJECT_EXECUTABLE_PATH}",
        shell=True,
    )

    if compile_process.returncode != 0:
        raise CompileFailedError


def compile_cmake(cmake_build_path):
    jobs = int(CPU_CORES * 1.5)

    cmake_path = None
    cmake_project = None
    with open(os.path.join(cmake_build_path, "CMakeCache.txt")) as cmake_cache_file:
        lines = cmake_cache_file.readlines()
        for line in lines:
            if line.startswith("CMAKE_COMMAND:INTERNAL="):
                cmake_path = line.strip().split("=")[1]
                break

    with open("CMakeLists.txt") as cmake_lists_file:
        lines = cmake_lists_file.readlines()
        for line in lines:
            if re.match(r"project\(.*\)", line.strip()):
                cmake_project = re.search(r"(?<=\()(.*)(?=\))", line).group()
                break

    if cmake_path is None:
        print(
            f"Couldn't find path to cmake in {Path(cmake_build_path).name}/CMakeCache.txt"
        )
        raise CompileSetupFailedError()

    if cmake_project is None:
        print("Couldn't find project name in CMakeLists.txt")
        raise CompileSetupFailedError()

    print(f"Detected CMake configuration for project {cmake_project}")
    print("Specify -g flag to skip detection and use g++ by default")
    print()

    compile_process = subprocess.run(
        f"{cmake_path} --build {os.path.abspath(cmake_build_path)} --target {cmake_project} -- -j {jobs}",
        shell=True,
    )

    if compile_process.returncode != 0:
        raise CompileFailedError

    shutil.copy(os.path.join(cmake_build_path, cmake_project), PROJECT_EXECUTABLE_PATH)


def compile(force_gcc=False):
    cmake_build_paths = glob.glob("cmake-build-*/")
    if (
        not force_gcc
        and os.path.exists("CMakeLists.txt")
        and cmake_build_paths
        and os.path.exists(os.path.join(cmake_build_paths[0], "CMakeCache.txt"))
    ):
        compile_cmake(cmake_build_paths[0])
    else:
        gcc_reason = (
            "(forced by argument)"
            if force_gcc
            else "(couldn't find CMake configuration)"
        )
        print(f"Using g++ compiler {gcc_reason}...")
        compile_gxx()


def diff_for_test_pair(input_file, output_file):
    run_process = subprocess.run(
        shlex.split(f"{PROJECT_EXECUTABLE_PATH} {input_file}"), stdout=subprocess.PIPE
    )

    if run_process.returncode != 0:
        raise ExecuteError

    diff_process = subprocess.Popen(
        shlex.split(f"diff --color=always - {output_file}"),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    stdout, _ = diff_process.communicate(run_process.stdout)

    return stdout.decode("utf-8")


def test_files_mapping(path, in_prefix, out_prefix):
    input_files = glob.glob(os.path.join(path, f"{in_prefix}*"))
    return [(f, f.replace(in_prefix, out_prefix, 1)) for f in input_files]


def run_test_case(pair):
    in_filename = Path(pair[0]).name
    print(f"{in_filename}... ", flush=True, end="")

    start_time = time.perf_counter()
    diff_output = diff_for_test_pair(*pair)
    elapsed = time.perf_counter() - start_time

    if diff_output:
        print(diff_output)

    passed = not diff_output

    # https://www.lihaoyi.com/post/BuildyourownCommandLinewithANSIescapecodes.html
    color = (32 if elapsed < 10 else 33) if passed else 31
    status_message = f"{'passed' if passed else 'failed'} in {elapsed:.2f}s"
    print(f"{color_wrap(status_message, color)}")

    return passed


def run_test_cases_group(test_file_pairs):
    return all(run_test_case(pair) for pair in test_file_pairs)


def test_example_io(project):
    print()
    print("Running example IO cases...")
    print()

    example_io_zip_path = Path(EXAMPLE_IO_ZIP_FILE_NAME.format(project))

    if not example_io_zip_path.exists():
        print(f"{example_io_zip_path.name} not found, downloading...")
        print()
        urllib.request.urlretrieve(
            TESTS_ZIP_URL.format(example_io_zip_path.name), example_io_zip_path
        )

    zipfile.ZipFile(example_io_zip_path).extractall(EXAMPLE_IO_PATH)
    test_file_pairs = test_files_mapping(EXAMPLE_IO_PATH, "in", "out")

    passed = run_test_cases_group(test_file_pairs)
    return passed


def test_pass_off(project):
    project_pass_off_zip_path = Path(PASS_OFF_CASES_ZIP_FILE_NAME.format(project))

    if not project_pass_off_zip_path.exists():
        print()
        print(f"{project_pass_off_zip_path.name} not found, downloading...")
        urllib.request.urlretrieve(
            TESTS_ZIP_URL.format(project_pass_off_zip_path.name),
            project_pass_off_zip_path,
        )

    zipfile.ZipFile(project_pass_off_zip_path).extractall(PASS_OFF_CASES_PATH)
    passoff_directories = os.listdir(PASS_OFF_CASES_PATH)

    passed = True
    for directory in passoff_directories:
        print()
        print(f"Running {directory.split('-')[1]}% pass-off cases...")
        print()
        test_file_pairs = test_files_mapping(
            os.path.join(PASS_OFF_CASES_PATH, directory), "input", "answer"
        )

        if not run_test_cases_group(test_file_pairs):
            passed = False
    return passed


TEST_CASE_GROUPS = [test_example_io, test_pass_off]


def run_all_test_cases(project, time_limit=None):
    using_user_time_limit = time_limit is not None
    effective_time_limit = (
        time_limit if using_user_time_limit else DEFAULT_TEST_SUITE_TIME_LIMIT_S
    )

    print()
    print(
        f"Using {'user-specified' if using_user_time_limit else 'default'} test suite time limit of {effective_time_limit} seconds"
    )

    start_time = time.perf_counter()
    passed = all([t(project) for t in TEST_CASE_GROUPS])
    elapsed = time.perf_counter() - start_time
    passed_time_limit = elapsed < effective_time_limit

    formatted_elapsed = f"{elapsed:.2f}s"
    if not passed:
        color = 31
        status_message = f"ERROR: Test(s) failed in {formatted_elapsed}"
    elif not passed_time_limit:
        color = 33
        status_message = f"WARNING: All tests passed but exceeded time limit: {formatted_elapsed} ({elapsed-effective_time_limit:.2f}s over max {effective_time_limit}s)"
    else:
        color = 32
        status_message = f"All tests passed in {formatted_elapsed}"

    print()
    print(color_wrap(status_message, color))

    return passed and passed_time_limit


def package(project):
    source_files = glob.glob("**.h") + glob.glob("**.cpp")
    output_zip = zipfile.ZipFile(OUTPUT_ZIP_FILE_NAME.format(project), "w")
    for source_file in source_files:
        output_zip.write(source_file)
    output_zip.close()


def is_schizo():
    df_name_process = subprocess.run(
        shlex.split("df . --output=source"), stdout=subprocess.PIPE
    )
    return (
        bool("dead.cs.byu.edu" in df_name_process.stdout.decode("utf-8"))
        if df_name_process.stdout
        else None
    )


def create_zip_schizo_link(project, filename):
    if not os.path.exists(PUBLIC_HTML_PATH):
        print("~/public_html not found, creating...")
        os.mkdir(PUBLIC_HTML_PATH)
        os.chmod(PUBLIC_HTML_PATH, 0o777)

    passoff_id = str(uuid.uuid4())
    Path(SCHIZO_LINK_PASSOFFS_PATH).mkdir(parents=True, exist_ok=True)

    passoff_filename = f"{passoff_id}.zip"
    passoff_file_path = os.path.join(SCHIZO_LINK_PASSOFFS_PATH, passoff_filename)

    shutil.copy(OUTPUT_ZIP_FILE_NAME.format(project), passoff_file_path)
    os.chmod(passoff_file_path, 0o777)

    return f"https://students.cs.byu.edu/~{getpass.getuser()}/labtest-passoffs/{passoff_filename}"


def schizo_export(project, zip_abspath):
    print("Creating temporary link for pass-off zip...")
    passoff_link = create_zip_schizo_link(project, zip_abspath)

    print()
    print(color_wrap(passoff_link, 32))
    print()
    print("Or copy to your machine with:")
    print(f'scp "{getpass.getuser()}@schizo:{zip_abspath}" .')
    print()

    if not sys.stdin.isatty():
        print("Reading data from stdin, can't wait for user input")
        return

    try:
        input("Press ctrl + c or enter to continue and delete temporary link... ")
    except KeyboardInterrupt:
        # Some shells won't insert a newline, leaving things looking wonky
        print()


@atexit.register
def cleanup():
    if Path(TESTER_DIR).exists():
        shutil.rmtree(TESTER_DIR)
    if Path(SCHIZO_LINK_PASSOFFS_PATH).exists() and sys.stdin.isatty():
        shutil.rmtree(SCHIZO_LINK_PASSOFFS_PATH)


def tester(project, force_gcc=False, time_limit=None):

    cleanup()
    Path(os.path.abspath(TESTER_DIR)).mkdir(exist_ok=True)

    print()
    print("🚀 Building and testing CS 236 project 4 🚀")

    try:
        print()
        print("--- Compiling ---")
        print()
        compile(force_gcc)
    except CompileFailedError:
        print()
        print(color_wrap("ERROR: Project failed to compile", 31))
        raise

    print()
    print("--- Running tests ---")

    passed = run_all_test_cases(project, time_limit)
    print()

    if not passed:
        print(color_wrap("Skipping export due to test errors or warnings", 33))
        raise TestsFailedError

    print("--- Exporting ---")
    print()

    zip_abspath = os.path.abspath(OUTPUT_ZIP_FILE_NAME.format(project))
    package(project)
    print(f"Writing zip to {zip_abspath}...")
    print()

    if is_schizo():
        print("🌠 Detected BYU CS filesystem 🌠")
        print()
        schizo_export(project, zip_abspath)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("project_number", type=int, help="number of target project")

    parser.add_argument(
        "-g",
        "--gcc",
        help="disable CLion CMake detection and always use g++ compiler",
        action="store_true",
    )

    parser.add_argument(
        "-t",
        "--time-limit",
        type=int,
        help="override default test suite time limit (useful for accounting for differences in execution speed between development and evaluation environments)",
    )

    args = parser.parse_args()

    try:
        tester(args.project_number, force_gcc=args.gcc, time_limit=args.time_limit)
    except (
        CompileFailedError,
        TestsFailedError,
        ExecuteError,
        CompileSetupFailedError,
    ) as e:
        print(e)
        exit(1)
