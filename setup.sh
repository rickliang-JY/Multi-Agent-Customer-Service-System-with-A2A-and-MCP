#!/bin/bash

# Multi-Agent Customer Service System - Setup Script

echo "================================"
echo "Multi-Agent System Setup"
echo "================================"
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "================================"
echo "Setup Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Set your API key:"
echo "   export ANTHROPIC_API_KEY=your_key_here"
echo ""
echo "3. Initialize the database:"
echo "   python database_setup.py"
echo ""
echo "4. Run test scenarios:"
echo "   python test_scenarios.py"
echo ""
echo "================================"
