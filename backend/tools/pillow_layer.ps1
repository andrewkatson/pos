# 1. Clean up previous attempts
if (Test-Path python) { Remove-Item -Recurse -Force python }
New-Item -ItemType Directory -Force -Path python

# 2. DISABLE default user settings (Fixes the conflict error)
$env:PIP_USER=$false

# 3. Install Linux version of Pillow
pip install Pillow `
    --platform manylinux2014_x86_64 `
    --target=python `
    --implementation cp `
    --python-version 3.14 `
    --only-binary=:all: `
    --upgrade

# 4. Zip it up
Compress-Archive -Path python -DestinationPath pillow-layer.zip -Force