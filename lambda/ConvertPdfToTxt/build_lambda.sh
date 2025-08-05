#!/bin/bash

# Navigate to the lambda function directory
cd /home/david/Github/patco-today-schedules/lambda/ConvertPdfToTxt

# Remove any existing packages/cache
rm -rf build/ *.zip __pycache__/ .pytest_cache/

# Create a clean build directory
mkdir build

# Install only production dependencies with no cache and no dev dependencies
pip install --no-cache-dir --no-deps -t build/ PyMuPDF==1.26.3

# Copy only the lambda function (exclude unnecessary files)
cp lambda_function.py build/

# Create the zip package, excluding unnecessary files
cd build
zip -r ../ConvertPdfToTxt.zip . \
    -x "*.pyc" \
    -x "*__pycache__*" \
    -x "*.dist-info*" \
    -x "*.egg-info*" \
    -x "*test*" \
    -x "*Test*" \
    -x "*/tests/*" \
    -x "*/test/*"

cd ..
rm -rf build/

echo "Lambda package created successfully: ConvertPdfToTxt.zip"
