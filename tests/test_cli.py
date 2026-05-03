# tests/test_cli.py
#
# Unit tests for the pyshield.py CLI module.
#
# These tests verify the argument parsing logic and the dispatch to handler
# functions.  Actual subcommand handlers (which call external tools) are
# tested via integration tests.  Here we only test argument parsing and the
# help output.

import sys          # Used to manipulate sys.argv in tests.

import pytest       # Provides test runner and assertion helpers.

# Import the parser builder from the CLI module.
from pyshield import build_parser


def test_build_subcommand_requires_source():
    """The 'build' subcommand should require the --source argument."""

    parser = build_parser()

    # Parsing without --source should raise SystemExit (argparse error).
    with pytest.raises(SystemExit):
        parser.parse_args(["build", "--entry", "main.py", "--output", "dist/"])


def test_build_subcommand_requires_entry():
    """The 'build' subcommand should require the --entry argument."""

    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["build", "--source", "src/", "--output", "dist/"])


def test_build_subcommand_requires_output():
    """The 'build' subcommand should require the --output argument."""

    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["build", "--source", "src/", "--entry", "main.py"])


def test_build_subcommand_parses_all_arguments():
    """The 'build' subcommand should parse all arguments correctly."""

    parser = build_parser()
    args = parser.parse_args([
        "build",
        "--source", "my_project/",
        "--entry", "main.py",
        "--output", "dist/",
        "--name", "myapp",
    ])

    assert args.source == "my_project/", "source should be 'my_project/'."
    assert args.entry == "main.py", "entry should be 'main.py'."
    assert args.output == "dist/", "output should be 'dist/'."
    assert args.name == "myapp", "name should be 'myapp'."


def test_build_subcommand_name_defaults_to_app():
    """The 'build' subcommand --name should default to 'app'."""

    parser = build_parser()
    args = parser.parse_args([
        "build",
        "--source", "src/",
        "--entry", "main.py",
        "--output", "dist/",
    ])

    assert args.name == "app", "Default name should be 'app'."


def test_license_generate_parses_all_arguments():
    """The 'license generate' subcommand should parse all arguments correctly."""

    parser = build_parser()
    args = parser.parse_args([
        "license", "generate",
        "--output", "my.lic",
        "--machine-lock",
        "--days", "30",
    ])

    assert args.output == "my.lic", "output should be 'my.lic'."
    assert args.machine_lock is True, "machine_lock should be True."
    assert args.days == 30, "days should be 30."


def test_license_generate_machine_lock_defaults_to_false():
    """The --machine-lock flag should default to False when omitted."""

    parser = build_parser()
    args = parser.parse_args([
        "license", "generate",
        "--output", "my.lic",
    ])

    assert args.machine_lock is False, "machine_lock should default to False."


def test_license_verify_parses_license_argument():
    """The 'license verify' subcommand should parse --license correctly."""

    parser = build_parser()
    args = parser.parse_args(["license", "verify", "--license", "product.lic"])

    assert args.license == "product.lic", "license should be 'product.lic'."


def test_hash_verify_parses_arguments():
    """The 'hash verify' subcommand should parse --file and --hash-file correctly."""

    parser = build_parser()
    args = parser.parse_args([
        "hash", "verify",
        "--file", "app.exe",
        "--hash-file", "app.exe.sha256",
    ])

    assert args.file == "app.exe", "file should be 'app.exe'."
    assert args.hash_file == "app.exe.sha256", "hash_file should be 'app.exe.sha256'."


def test_obfuscate_subcommand_parses_arguments():
    """The 'obfuscate' subcommand should parse --source and --output correctly."""

    parser = build_parser()
    args = parser.parse_args([
        "obfuscate",
        "--source", "my_project/",
        "--output", "obfuscated/",
    ])

    assert args.source == "my_project/", "source should be 'my_project/'."
    assert args.output == "obfuscated/", "output should be 'obfuscated/'."
