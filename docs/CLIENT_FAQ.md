# Client FAQ: PyShield Python Code Protection

This document answers the questions clients most commonly ask about PyShield. It is written to be direct and honest. Some answers include caveats that a less candid vendor would omit. We include them because a client who understands the limits is easier to work with than one who expects magic.

## Can the protection be cracked?

Yes, eventually, by a determined and skilled attacker with enough time. No software protection is mathematically uncrackable. This is true of every approach, including ours, Cython, Nuitka, commercial packers, and even code that runs in secure enclaves.

What PyShield does is make cracking expensive enough that a typical attacker will give up or choose a different approach. The goal is economic deterrence, not absolute prevention. We recommend reading LIMITATIONS.md for a full explanation of this position.

## How is this different from just compiling Python with Cython or Nuitka?

Cython compiles Python to C and then to a native extension. Nuitka compiles Python to C and then to a standalone binary. Both of these approaches produce code that is significantly harder to read than plain Python, but both leave the native machine code in the binary, and that code can be disassembled and decompiled with standard tools. The algorithm structure, including logic branches and numeric constants, is often recoverable with moderate effort.

PyArmor takes a different approach. It encrypts the Python bytecode entirely and only decrypts it in memory at the moment it is needed. The decryption key is embedded in a native runtime extension that is more difficult to analyse than straightforward compiled Python. The result is that the algorithm logic is not visible in the binary in the same way it is with Cython or Nuitka output.

The tradeoff is that PyArmor protection carries a small runtime overhead because of the decryption step, and it requires the PyArmor runtime to be bundled with the binary. PyInstaller handles the bundling transparently.

## Why PyArmor and not some other tool?

We evaluated several options. PyArmor has been maintained since 2008, supports Python 3.11 and later, has documented compatibility with PyInstaller, and works on all three major platforms: Windows, Linux, and macOS. It provides the specific combination of bytecode encryption and license binding that the use case requires.

Alternatives like Nuitka produce faster binaries but provide weaker IP protection because the algorithm logic is compiled to native code that is analysable with standard disassemblers. Commercial products like Themida or VMProtect are designed for native executables, not Python, and add complexity without matching PyArmor's Python-specific protections.

For the free tier of PyArmor, which we use by default, the protections are strong for most commercial deployments. PyArmor also offers a paid Pro tier with JIT compilation and additional obfuscation techniques, which we can enable if a client needs the highest available protection.

## Does the protected binary need internet to run?

No. The protected binary is entirely self-contained. The license validation is performed locally on the user's machine by checking the machine ID and expiry date. No network calls are made during runtime.

This is by design. Requiring internet connectivity would create a dependency on our servers being available, and many enterprise deployments happen in environments with restricted network access or no internet at all.

The tradeoff of local validation is documented in LIMITATIONS.md: a patched binary could theoretically skip the validation. If remote validation is required, we can discuss integrating a server-side activation check.

## What happens if my user's antivirus flags the binary?

This is a common issue with any PyInstaller-packaged binary. Antivirus software uses heuristic analysis, and a self-extracting Python archive that decrypts code in memory matches the behavioural signature of malware, even when it is entirely benign.

The practical solutions are: have the binary code-signed with a code-signing certificate from a trusted certificate authority, which tells Windows and macOS that the binary was signed by a known publisher; submit the binary to the antivirus vendors for whitelisting; or distribute the binary through your own signed installer package.

Code signing is the most reliable solution and we recommend it for any commercial deployment. The cost of a code-signing certificate for an organisation is typically a few hundred dollars per year.

## Can we revoke a license remotely?

Not with the current implementation. Licenses are validated locally, so a license that has been issued cannot be "called back" remotely. The tools available without server-side infrastructure are setting an expiry date (the license stops working on that date) and generating a replacement license that does not include the old machine ID.

If you need true remote revocation (the ability to invalidate a license at any time regardless of expiry date), we would need to implement a check-in service that the binary contacts periodically. This is feasible but adds significant complexity and requires you to operate a service.

## How do we update a deployed binary?

Distributing an updated binary follows the same process as the initial distribution. You build the new version with PyShield, produce platform-specific binaries, and deliver them to your users through whatever update mechanism you currently use. If you are using expiry-dated licenses, no license change is required unless you want to change the expiry date.

There is no automatic update mechanism built into PyShield itself. The binary does not phone home to check for updates. This is intentional: it avoids requiring internet connectivity and avoids the complexity of an auto-update system. If automatic updates are required, they would need to be implemented as a separate component outside PyShield.

## What Python versions are supported?

PyArmor 8 supports Python 3.8 through 3.12. The PyShield codebase itself targets Python 3.11 and is tested on Python 3.11 in CI. If you need a different Python version, we can test compatibility, but 3.11 is our supported and tested baseline.

## Does this work on ARM Macs?

Yes. PyArmor supports Apple Silicon (arm64) natively as of version 8. PyInstaller also supports Apple Silicon. The CI matrix includes macOS runners, though the macOS end-to-end tests are currently marked as best-effort while we validate the full build pipeline on Apple Silicon hardware. Unit tests pass on macOS.

For a production deployment to ARM Macs, the binary should be built on an ARM Mac runner (macOS-latest on GitHub Actions runs on Apple Silicon). A binary built on an Intel Mac will run on an ARM Mac through Rosetta 2 emulation, but a native ARM build will be faster and avoid the emulation overhead.

## Can someone extract the embedded license secret?

The HMAC key used to sign licenses is embedded in the protected binary as part of the obfuscated Python code. After PyArmor protection, this key is encrypted and not visible as a readable string in the binary. However, as documented in LIMITATIONS.md, a sufficiently determined attacker who captures the decrypted bytecode from memory could extract the key and use it to generate unlimited valid licenses.

In the default open-source configuration of PyShield, a fixed well-known HMAC key is used. For a production deployment with real commercial value at stake, we recommend replacing this key with a per-deployment secret that is generated during the build process. This is a one-line change in src/license_manager.py and license_check.py. We can assist with this customisation.
