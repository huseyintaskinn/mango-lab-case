#!/usr/bin/env bash
# Runs your tests. They must pass with no network at all: we run this with
# FX_UPSTREAM_BASE pointing at a closed port.
set -eu

export FX_UPSTREAM_BASE="http://localhost:1" # kapali port
pytest test_main.py
