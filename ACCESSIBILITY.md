# Accessibility

This document explains how PyShield is maintained with screen-reader accessibility in mind. The repository owner uses a screen reader full-time due to 20/400 vision.

## Coding Conventions

Every source file contains heavy line-by-line comments. Each comment is written in plain English and explains what the following line or block does. Comments are written to be read aloud without losing meaning.

No ASCII diagrams, box-drawing characters, or alignment-based formatting are used anywhere in the source code or documentation. Alignment padding (using spaces to line up columns) is avoided because screen readers read each character and aligned columns create confusing output.

All documentation files are written as plain prose. Bullet lists are used sparingly and only where a list genuinely helps comprehension.

## File and Folder Names

All file names use lowercase letters and underscores. Mixed-case names or names that rely on visual distinction between similar characters are avoided.

## Error Messages

Error messages produced by the CLI and the library are written as complete sentences. They identify the problem and, where possible, suggest what the user should check or do next. Terse or cryptic error codes are not used.

## CLI Output

The CLI prints one message per action. Each message is a complete sentence. Progress messages begin with the word "Running" or "Writing" or another active verb so the screen reader can announce what is happening without the user needing to read the full line.

## Test Output

Test names are written as plain English sentences in snake_case. For example, "test_verify_license_rejects_wrong_machine_id" describes exactly what is being tested. This makes the pytest output meaningful when read by a screen reader.

## How to Contribute

If you submit a pull request, please follow the same conventions described in this file. Add line-by-line comments to any new code. Write docstrings as complete sentences. Do not use ASCII diagrams in documentation. Write error messages as complete sentences.

If you are unsure whether a change is accessible, open an issue and describe the change in plain language. The maintainer will review it.
