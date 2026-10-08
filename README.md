# JobTrack

A local command-line job application tracker for Windows.

## Install

1. Install [Python 3.14](https://www.python.org/downloads/windows/) and [Git for Windows](https://git-scm.com/download/win). Enable the Python PATH option during installation, then open a new PowerShell window.
2. Install JobTrack:

   ```powershell
   py -3.14 -m pip install "git+https://github.com/ericliceatapia/job-track.git"
   ```

3. Initialize your database and start tracking:

   ```powershell
   jt db
   jt add
   jt list
   jt --help
   ```

If `jt` is not recognized, add the Scripts directory shown in pip's installation warning to your user PATH, then reopen your terminal. No repository clone or virtual-environment activation is required.

Your data stays on your machine at `%USERPROFILE%\AppData\Local\JobTrack\jobtrack.db`.

## Update

```powershell
py -3.14 -m pip install --upgrade "git+https://github.com/ericliceatapia/job-track.git"
```
