# Security Policy

## Supported Versions

This is a hobby project maintained by a single developer. 
**Only the latest released version is supported.** 

| Version | Supported |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| Older   | :x:                |

## Reporting a Vulnerability

I take security seriously, but please remember this is a volunteer effort.

**Do not open a public issue for security vulnerabilities.**

Instead, please use GitHub's Private Vulnerability Reporting feature:

1.  Navigate to the **Security** tab in this repository.
2.  Click on **Report a vulnerability** (or look for the "Advisories" section).
3.  Fill out the form with details about the exploit or vulnerability.

This ensures the issue is discussed privately between us before being disclosed to the public.

**Response Expectations:**
I will try to acknowledge your report as soon as possible. However, as this is a hobby project provided for free, there is no Service Level Agreement (SLA) for fixes.

## Binary Safety & Antivirus Warnings

### "False Positives"
This application is distributed as an unsigned Windows Executable (`.exe`). 
Because I am an individual developer and do not purchase expensive code-signing certificates, Windows Defender or other Antivirus software may flag this application as "Unknown" or "Suspicious".

This is a known, common issue with Python applications packaged with PyInstaller.

**To verify safety:**
1.  Run the executable through a virus scanner of your choice.
2.  Alternatively, clone this repository, inspect the code, and run it directly from source using Python.

**I assume no liability for the execution of binary files. If you do not trust the binary, please run from source.**