# examples/demo_app/main.py
#
# The command-line entry point for the Acme Corp data-processing demo application.
#
# Usage:
#   python main.py process <input.csv> <output.csv> [--license <path>]
#
# The "process" subcommand reads a customer CSV file, computes a churn-risk
# score for each row using the proprietary algorithm in secret_algorithm.py,
# and writes the results to the output CSV file.
#
# If --license is provided, the license file is validated before any
# processing begins.  An invalid, expired, or wrong-machine license causes
# an immediate exit with a clear error message.
#
# Progress is reported as "Step X of Y: <description>" so that screen-reader
# users hear each step as it happens.
#
# This module has no external dependencies beyond the Python standard library
# and the two sibling modules: secret_algorithm and data_loader.

import argparse        # Standard library: parse command-line arguments.
import sys             # Standard library: sys.exit and sys.stderr.
import os              # Standard library: path manipulation.

# Import the sibling modules.  These are bundled alongside main.py by PyInstaller.
import secret_algorithm   # Contains the proprietary churn-risk scoring function.
import data_loader        # Contains load_csv and write_csv.
import license_check      # Contains validate_license for runtime license enforcement.


def cmd_process(args: argparse.Namespace) -> int:
    """Run the data-processing pipeline: load, score, and write.

    Args:
        args: Parsed command-line arguments.  Expected attributes:
              - input: Path to the input CSV file.
              - output: Path where the output CSV will be written.
              - license: Optional path to a PyShield license file.

    Returns:
        An integer exit code.  0 means success; 1 means failure.
    """

    # Count the total number of steps so progress messages say "Step X of Y".
    # The steps are: (1) validate license if provided, (2) load input,
    # (3) compute scores, (4) write output.  Step 1 is conditionally counted.
    if args.license:
        # License validation is Step 1 of 4 when a license is provided.
        total_steps = 4
        step_offset = 0
    else:
        # Without a license, we have 3 steps.
        total_steps = 3
        step_offset = 1   # Offset so the first real step is still labeled sensibly.

    # --- Step 1 (conditional): Validate the license file. ---
    if args.license:
        print(f"Step 1 of {total_steps}: Validating license file: {args.license}")
        try:
            license_check.validate_license(args.license)
            print("License is valid.")
        except FileNotFoundError as exc:
            # The license file does not exist.
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        except ValueError as exc:
            # The license failed validation (expired, wrong machine, bad signature).
            print(f"Error: License validation failed. {exc}", file=sys.stderr)
            return 1

    # --- Step 2 (or 1 if no license): Load the input CSV file. ---
    load_step = 1 + (0 if args.license else 0)
    actual_step = load_step if not args.license else 2
    print(f"Step {actual_step} of {total_steps}: Loading input file: {args.input}")

    try:
        rows = data_loader.load_csv(args.input)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: Input file has a problem. {exc}", file=sys.stderr)
        return 1

    print(f"Loaded {len(rows)} customer records.")

    # --- Step 3 (or 2 if no license): Compute churn-risk scores. ---
    score_step = actual_step + 1
    print(f"Step {score_step} of {total_steps}: Computing churn-risk scores.")

    # Process each row, adding a "churn_risk" column.
    scored_rows = []
    for row in rows:
        try:
            # Call the proprietary scoring function from secret_algorithm.
            risk = secret_algorithm.compute_churn_risk(row)
            # Add the computed score to a copy of the row dictionary.
            scored_row = dict(row)  # Copy so we do not modify the original.
            scored_row["churn_risk"] = f"{risk:.6f}"  # Format to 6 decimal places.
            scored_rows.append(scored_row)
        except (KeyError, ValueError) as exc:
            # A row is missing a column or contains a non-numeric value.
            customer_id = row.get("customer_id", "unknown")
            print(
                f"Error: Could not score customer {customer_id}. {exc}",
                file=sys.stderr,
            )
            return 1

    print(f"Scored {len(scored_rows)} records successfully.")

    # --- Step 4 (or 3 if no license): Write the output CSV file. ---
    write_step = score_step + 1
    print(f"Step {write_step} of {total_steps}: Writing output file: {args.output}")

    try:
        data_loader.write_csv(args.output, scored_rows)
    except (ValueError, OSError) as exc:
        print(f"Error: Could not write output file. {exc}", file=sys.stderr)
        return 1

    print(f"Output written to: {args.output}")
    print("Processing complete.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build and return the command-line argument parser.

    Returns:
        An argparse.ArgumentParser with the 'process' subcommand registered.
    """

    # Create the top-level parser.
    parser = argparse.ArgumentParser(
        prog="demo_app",
        description=(
            "Acme Corp data processor: reads a customer CSV, scores each "
            "customer for churn risk using a proprietary algorithm, and "
            "writes the scored output to a new CSV file."
        ),
    )

    # Create a subparser group for subcommands.
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # --- 'process' subcommand ---
    process_parser = subparsers.add_parser(
        "process",
        help="Score customers for churn risk and write the output CSV.",
        description=(
            "Load an input CSV, compute a churn-risk probability for each "
            "customer, and write the results to an output CSV."
        ),
    )

    # Positional argument: the input CSV file.
    process_parser.add_argument(
        "input",
        help="Path to the input CSV file containing customer data.",
    )

    # Positional argument: the output CSV file.
    process_parser.add_argument(
        "output",
        help="Path where the scored output CSV will be written.",
    )

    # Optional argument: path to a PyShield license file.
    process_parser.add_argument(
        "--license",
        default=None,
        metavar="LICENSE_FILE",
        help=(
            "Path to a PyShield license file.  If provided, the license is "
            "validated before processing begins.  Exits with an error if the "
            "license is invalid, expired, or bound to a different machine."
        ),
    )

    # Register the handler for this subcommand.
    process_parser.set_defaults(func=cmd_process)

    return parser


def main() -> int:
    """Parse arguments and dispatch to the appropriate subcommand handler.

    Returns:
        The integer exit code from the subcommand handler (0 = success).
    """

    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


# Standard Python entry-point guard: only call main() when running as a script,
# not when imported as a module (e.g., during testing).
if __name__ == "__main__":
    sys.exit(main())
