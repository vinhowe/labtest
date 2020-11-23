# labtest

Absurdly self-contained testing script for BYU CS 236.

Only tested to work Fall 2020. Fork this project if you want to support a different semester.

## Usage

Just open `bash` or `fish`, `cd` to the directory with all of your source filess

### bash
```bash
python3 <(curl -s https://raw.githubusercontent.com/vinhowe/labtest/main/labtest.py) <lab number>
```

### fish
```fish
python3 (curl -s https://raw.githubusercontent.com/vinhowe/labtest/main/labtest.py | psub) <lab number>
```

## Features

* Automatically detects existing CMake configurations for faster builds
* Downloads and extracts test cases automatically
* Runs and times all test cases
* Cleans up extracted test cases when finished
* Exports zip ready for pass-off if tests finish
* Detects if you are on one of BYU's Schizo open lab machines (using deadfs) and generates a temporary URL to let you download exported zip
