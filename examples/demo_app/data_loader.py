# examples/demo_app/data_loader.py
#
# This module handles reading and writing the customer CSV files that the
# demo app processes.
#
# Two public functions are provided:
#   load_csv(path)          — reads a CSV file and returns a list of dicts.
#   write_csv(path, rows)   — writes a list of dicts to a CSV file.
#
# Both functions validate that required columns are present and raise clear
# error messages if something is wrong, so users with screen readers can
# understand exactly what needs to be fixed.

import csv  # Standard library module for reading and writing CSV files.
import os   # Used to check that the file exists before trying to read it.


# The set of column names that every input row must contain.
# If any of these is missing, load_csv raises a clear error.
REQUIRED_COLUMNS = frozenset(
    ["customer_id", "age", "income", "tenure_months", "product_count", "support_tickets"]
)


def load_csv(path: str) -> list:
    """Read a CSV file and return its rows as a list of dictionaries.

    The first row of the file must be a header row.  Each subsequent row
    becomes a dictionary with the column names as keys.

    Args:
        path: The path to the CSV file to read.

    Returns:
        A list of dictionaries.  Each dictionary represents one data row,
        with column names as keys and cell values as string values.
        The list is empty if the file has no data rows (only a header).

    Raises:
        FileNotFoundError: If the file at `path` does not exist.
        ValueError: If the header row is missing any required column name.
    """

    # Resolve the path so any error message shows the full path.
    path = os.path.abspath(path)

    # Confirm the file exists before opening it, so the error is clear.
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Input file does not exist: {path}"
        )

    # Open the file in text mode with UTF-8 encoding.
    # newline='' tells Python not to do any line-ending translation,
    # which is required by the csv module documentation to handle all
    # line-ending styles correctly.
    with open(path, newline="", encoding="utf-8") as csv_file:
        # DictReader uses the first row as column names automatically.
        reader = csv.DictReader(csv_file)

        # reader.fieldnames is populated when the first row is read.
        # We read it by accessing the property, which triggers the first read.
        header_columns = set(reader.fieldnames or [])

        # Check that every required column is present in the header.
        missing = REQUIRED_COLUMNS - header_columns
        if missing:
            # Sort the missing column names for a consistent error message.
            missing_sorted = sorted(missing)
            raise ValueError(
                f"Input file is missing required columns: {missing_sorted}. "
                f"File: {path}"
            )

        # Read all data rows into a list.  Each row is a dict keyed by column name.
        rows = list(reader)

    # Return the list of row dictionaries.
    return rows


def write_csv(path: str, rows: list) -> None:
    """Write a list of row dictionaries to a CSV file.

    The column names are taken from the keys of the first row.  All rows
    are written in the same column order.  If the list is empty, a file
    with no rows is written (just the header if fieldnames can be inferred,
    or an empty file otherwise).

    Args:
        path: The path where the CSV file should be written.  Parent
              directories must already exist.
        rows: A list of dictionaries.  Every dictionary must have the same
              set of keys.  Values are written as-is (converted to strings
              by the csv module).

    Returns:
        None

    Raises:
        ValueError: If `rows` is empty (we cannot infer column names).
        OSError: If the file cannot be written (e.g., permission denied).
    """

    # We need at least one row to know what the columns are.
    if not rows:
        raise ValueError(
            "Cannot write an empty list of rows: column names cannot be determined."
        )

    # Get the column names from the first row's keys.
    fieldnames = list(rows[0].keys())

    # Open the output file for writing.
    # newline='' is required by the csv module to prevent double line endings
    # on Windows (the csv module handles line endings itself).
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        # Create a DictWriter with the column names from the first row.
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
            lineterminator="\n",  # Always use Unix line endings for cross-platform consistency.
        )

        # Write the header row (column names).
        writer.writeheader()

        # Write all data rows.
        writer.writerows(rows)
