# labtest

Absurdly self-contained testing/export script for BYU CS 236.

Detects if you're on Schizo and automatically generates a URL to download your exported zip.

Only tested to work Fall 2020. Fork this project if you want to support a different semester.

## Usage

Just open `bash` or `fish` (if you don't know what I'm talking about, just use the `bash` command),
`cd` to the directory containing source files for your project, and run the command listed
for your shell

### `bash`
```bash
python3 <(curl -s https://raw.githubusercontent.com/vinhowe/labtest/main/labtest.py) <lab number>
```

### `fish`
```fish
python3 (curl -s https://raw.githubusercontent.com/vinhowe/labtest/main/labtest.py | psub) <lab number>
```

## Features

* Automatically detects existing CMake configurations for faster builds
* Downloads and extracts test cases automatically
* Runs and times all test cases
* Cleans up extracted test cases when finished
* Exports zip ready for pass-off if tests finish
* Detects if you are on one of BYU's Schizo open lab machines (using deadfs) and generates a temporary
URL to let you download exported zip
