"""Append the Panzer IV C to the cumulative Panzer II F / BT-7 / Barbarossa resource kit."""

import argparse
import json
from pathlib import Path

from ..panzer2f.integration import build
from .source import ID


def main():
    c = argparse.ArgumentParser(description=__doc__)
    for key in ("apk", "base", "previous", "player", "ai-dir", "out"):
        c.add_argument("--" + key, type=Path, required=True)
    print(
        json.dumps(
            build(
                **vars(c.parse_args()),
                vehicle=ID,
                previous_id="Panzer_II_Ausf_F",
                stem="PanzerIV-C.overlay",
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
