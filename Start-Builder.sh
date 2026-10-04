#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 -m tankbuilder gui
