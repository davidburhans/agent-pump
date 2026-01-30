@echo off
pushd ..
echo Starting verification process...

echo Running tests...
python -m pytest tests/unit/test_verification_executor.py -v
if %errorlevel% neq 0 (
    echo Tests failed with exit code %errorlevel%
) else (
    echo Tests passed
)

echo Running ruff check...
python -m ruff check .
if %errorlevel% neq 0 (
    echo Ruff check failed with exit code %errorlevel%
) else (
    echo Ruff check passed
)

echo Running pyright...
python -m pyright
if %errorlevel% neq 0 (
    echo Pyright check failed with exit code %errorlevel%
) else (
    echo Pyright check passed
)

echo Verification complete.
popd