#!/bin/bash
cd "$(dirname "$0")"
exec .venv/bin/python "$PWD/relay.py" >> relay.log 2>&1
