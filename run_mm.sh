#!/bin/bash
# Money Machines script runner
# Clears conflicting PYTHONPATH and sets up the venv properly
export PYTHONPATH="/path/to/project/money-machines/shared/scripts:/path/to/project/money-machines/.venv/lib/python3.12/site-packages"
export VIRTUAL_ENV="$HOME/money-machines/.venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"

# Run the script with the venv python
exec "$VIRTUAL_ENV/bin/python3" "$@"
