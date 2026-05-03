# Limitations of PyShield

This document is written to be read first, not buried in the appendix. It exists because presenting honest constraints up front establishes the kind of trust that helps a client relationship survive the inevitable hard question. The author of this tool recommends giving this document to your client before they ask.

## What PyShield does well

PyShield raises the cost of reverse engineering from a matter of minutes to a realistic minimum of days or weeks for a skilled attacker, often much longer for an unskilled one. In practice, most competitors who might try to steal your algorithm are not running dedicated security research operations. They are engineers who would look at your binary, spend an hour or two, give up, and write their own version instead.

Specifically, PyShield achieves the following.

The source code is not recoverable as readable Python files. PyArmor encrypts the bytecode so that a standard disassembler like uncompyle6 or decompile3 produces either garbage or nothing at all. The algorithm constants, variable names, and logic structure are not visible in the binary.

The license system enforces who can run the software and for how long. A license file locked to a specific machine ID will not work on any other machine. An expiry-dated license stops working on a given date. Both constraints are enforced by cryptographic signing, so a user who edits the license file will have an invalid signature and the software will refuse to run.

Tamper detection records a SHA-256 fingerprint of the binary at build time. If the binary is modified after delivery, the fingerprint will no longer match, and the verification tool will report a tamper event.

Anti-debug checks detect common debuggers and refuse to run under them, raising the cost of runtime analysis.

The build process is reproducible and automated. Every protected binary is produced by the same pipeline on the same classes of hardware, so you can confidently deliver a build to a client knowing it was produced by a tested process.

## What PyShield cannot prevent

It is important to say this plainly: no software protection system, including the most expensive commercial code-protection products on the market, can make a program truly unbreakable. This is not a weakness specific to PyShield. It is a fundamental property of how computers work.

If software runs on a user's hardware, that user can, in principle, observe everything the software does. They can attach a debugger, take a memory dump, use a hardware logic analyser, or simply watch the network traffic. Given enough time, skill, and motivation, a determined attacker can reconstruct the logic of any program.

The goal of protection is not to prevent this permanently. The goal is to make it expensive enough that the attacker decides it is not worth the effort.

## Specifically: PyArmor can be unwrapped by a determined attacker

PyArmor works by encrypting your Python bytecode and loading a runtime extension that decrypts it in memory just before execution. This means that at the moment your code runs, the decrypted bytecode exists in memory.

A skilled attacker can write a custom Python runtime that intercepts the decryption call, captures the decrypted bytecode, and serialises it back to a .pyc file. Tools for doing this exist, though they require meaningful effort to use correctly and more effort to apply to a custom PyArmor build.

The short version: PyArmor is strong protection against casual inspection and against moderately motivated attackers. It is not strong protection against a well-funded, focused security researcher who has weeks to spend.

## Specifically: a memory dump reveals decrypted bytecode

When your code is running, the decrypted bytecode and the Python objects it creates (including the algorithm constants and intermediate results) exist in the process's virtual memory. On most operating systems, a process with appropriate privileges can read another process's memory. On Linux, this is done with the ptrace system call or by reading from /proc/pid/mem. On Windows, it is done with ReadProcessMemory.

PyShield includes anti-debug checks that detect common debuggers, but these checks are not foolproof. A sufficiently creative attacker can work around them.

The implication: if an attacker has administrative access to the machine running your protected software, the memory dump approach becomes feasible. This is why "server-side execution" (see below) is the strongest protection for truly high-value algorithms.

## Specifically: license validation is local — a patched binary can skip it

The license validation logic runs inside the protected binary on the user's machine. This means a sufficiently skilled attacker can patch the binary to skip the validation check entirely. Because the binary is running on hardware the attacker controls, there is no way for the software to stop them from modifying it.

In practice, patching a PyArmor-protected binary is significantly harder than patching a plain Python script, because the validation logic is inside the encrypted bytecode. But it is not impossible.

With per-build secrets, an attacker who reverse-engineers one customer's binary cannot use the recovered HMAC key to forge licenses for any other customer. Each build embeds its own independently generated key, so the blast radius of a single compromise is limited to that one build. An attacker who wants to target a second customer must repeat the full reverse-engineering effort against that customer's binary.

Remote license validation (phoning home to a server to check the license) would be stronger. PyShield does not implement remote validation in its current form. If you need it, consider pairing PyShield with a server-side activation service.

## Why this is still worth doing — the economic argument

The argument for protection is not that the protection is perfect. The argument is that it raises the attacker's cost above the value they expect to gain.

Consider a competitor who wants to steal your churn-scoring algorithm. Without protection, they download your binary, open it in a Python decompiler, and read the weights in under an hour. Total cost: one hour of an engineer's time.

With PyShield protection, they need to set up a custom memory-capture harness, work through PyArmor's obfuscation layer, reconstruct the bytecode, and then make sense of it. Realistic cost: two to four weeks of a skilled engineer's time, assuming they do not give up first.

At a fully-loaded cost of even fifty dollars per hour, that is between four thousand and eight thousand dollars in labour — to steal an algorithm they could build themselves for the same cost. For most real-world situations, this calculation makes the attack economically unattractive.

That is the honest enterprise pitch: we make reverse engineering more expensive than alternatives.

## When to use additional measures (server-side execution, hardware tokens)

If your algorithm is genuinely high-value and you are deploying to untrusted hardware (hardware the customer controls), consider the following additional measures.

Server-side execution means your algorithm runs on your servers and the customer's software sends inputs and receives outputs over a network. The algorithm itself never leaves your infrastructure. No amount of binary analysis can recover code that never runs on the attacker's machine. The tradeoff is latency, internet dependency, and infrastructure cost.

Hardware security modules, also called HSMs, are physical devices that perform cryptographic operations inside tamper-resistant hardware. Some high-security deployments use HSMs to hold the decryption key for the algorithm, so the key is never present in software memory. This is very expensive and complex to implement.

Hardware license dongles are a middle ground. The dongle holds a secret that the binary requires to run. Copying the software without the dongle is useless. The main tradeoff is user friction: the dongle must be physically present at the machine that runs the software.

For most commercial software deployments, PyShield provides a reasonable level of protection at low cost. For truly critical algorithms that represent hundreds of thousands of dollars of research value, the server-side model is the correct approach.
