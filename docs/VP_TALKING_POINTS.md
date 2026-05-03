# VP Talking Points: PyShield Demo Meeting

Use this document to prepare for the meeting. Read it aloud once before you go in. The points are ordered to match how the conversation typically flows.

## Opening: what you have built

PyShield is an enterprise Python code-protection pipeline. It combines PyArmor bytecode encryption, PyInstaller single-file packaging, cryptographic license binding, and tamper detection into one repeatable, automated build process.

The deliverable is a protected binary for Windows, Linux, and macOS. Users cannot read the source code. They cannot run the software without a valid license. If they modify the binary, the modification is detectable.

## How the protection was verified

Protection is verified by automated tests in CI, not by visual inspection.

This is the most important point for a VP or technical lead to hear. The honest answer to "how do you know it works?" is not "I looked at the output." It is: there is a test suite that builds the demo application, reads the binary as raw bytes, and asserts that the proprietary strings and algorithm constants do not appear anywhere in it. The test fails if protection is broken. That test runs on every code change, on Microsoft-hosted servers, with a public log.

To run the tests live in the meeting:

    pytest -m e2e -v

Each test prints its name and pass or fail status on a separate line, which reads clearly on a screen reader and is easy to follow on a projected screen.

## What CI does for you

Builds run on Microsoft's hosted Windows, Linux, and macOS runners. No separate hardware is required. When you push a tag, GitHub Actions spins up a fresh server on each platform, installs the dependencies, runs the obfuscation and packaging pipeline, and runs the tests. The binary artifacts are available for download from the Actions run summary.

This means you do not need to own a Mac to build a Mac binary, or a Windows machine to build a Windows executable. The cost is included in the GitHub account.

## The honest protection pitch

We make reverse engineering economically unattractive. That is the honest enterprise pitch.

After PyArmor protection, the algorithm source code is not recoverable by standard tools. Recovering it requires a custom memory-capture setup and substantial expertise. Realistic time cost: days to weeks of skilled engineering work.

A competitor who would otherwise decompile the binary in an hour now faces a cost-benefit decision. If the algorithm was worth that much to steal, it was worth paying a license fee for.

## What to say if asked "is this uncrackable?"

No protection is uncrackable. Saying otherwise is unprofessional and will damage your credibility the first time a technically informed person in the room presses you on it.

The correct answer is: no protection is absolute, but the goal is raising the economic cost of an attack above the value an attacker expects to gain. If stealing your algorithm requires four weeks of a skilled engineer's time, and that engineer costs your competitor fifty dollars an hour, the attack costs eight thousand dollars. For most commercial situations, that cost exceeds the expected benefit, and the attacker moves on.

This framing is also what separates a credible engineer from a vendor making marketing claims. Leading with it, rather than waiting to be pressed, signals that you have thought seriously about the problem.

## LIMITATIONS.md and why to share it

Share LIMITATIONS.md with the client before they ask. Do not hide it.

The document lists what PyShield cannot do: PyArmor can be unwrapped by a determined attacker, a memory dump reveals decrypted bytecode, and license validation is local so a patched binary can skip it. It also explains why the protection is still worth deploying in most commercial contexts.

A client who reads this document first will trust you more, not less. A client who discovers these limitations later, without having been told, will trust you less and may feel they were misled.

The document exists specifically to be shown to clients and VPs up front.

## Quick reference: commands for the live demo

To build the demo application (takes about one minute on a fresh environment):

    ./examples/demo_app/build_demo.sh

To run only the end-to-end tests that prove protection:

    pytest -m e2e -v

To run all unit tests (no PyArmor or PyInstaller required, completes in seconds):

    pytest -m "not e2e" -v

To generate a license and run the protected binary:

    python pyshield.py license generate --output demo.lic --machine-lock --days 365
    ./dist/demo/main process examples/demo_app/sample_input.csv /tmp/out.csv --license demo.lic
