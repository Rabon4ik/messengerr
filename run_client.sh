#!/bin/bash
source venv/bin/activate
export PYTHONPATH=.
python client/client.py "$@"
