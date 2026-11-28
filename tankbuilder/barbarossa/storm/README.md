# Barbarossa 02: Stormbreak

This generator operates on the previous T-28 / Panzer III F staging area, the previous signed
`Hatch-0.4-Barbarossa-Complete.apk`, and its first-mission `mission.json`. The input files and APK are read-only. Use the repository's builder dependencies and SciPy for PCM synthesis. The signed-release steps are separate.

- `build.py` produces the four native playable scenes, the two-row menu, the registered BT-7 player, the cumulative overlay, the loose stream and the manifest. The three new III F vehicles reuse the first mission's original wave-2 root IDs, trigger references and world positions.
- `deployment.py` uses the original terrain and collision-aware game waypoint builder for the selectable rosters. Units have persistent identities; selecting a side consumes one player slot.
- `weather.py`, `lightning.py` and `sound.py` author the scene-local particle and lighting effects and the original rain and thunder banks. Lightning is a timed native light plus one of three non-colliding sky meshes. Rain and thunder use the game's AudioSources and the correct Android streaming-resource path.
- `verify.py` reopens the packed UnityFS, including every published scene, checks the menu's real labels and actions, individual vehicles/routes, results, weather callbacks and resource keys, and decodes each sound bank to the original PCM.
- `preview.py` plots the manifests at the same scale on the actual terrain. `kit.py` bundles the two new .hatch modules, current catalog and AI index, resource patch, sound, DEX and ARM64 companion with the standalone Python 3 restorer. No signing material is needed.

From the repository root, with `out` and `compiled` set to build output directories:

```sh
python -m tankbuilder.barbarossa.storm.build --staged "$staged" --apk "$apk" --mission "$mission" --out "$out"
python -m tankbuilder.barbarossa.storm.verify --staged "$staged" --legacy "$mission" --out "$out"
python -m tankbuilder.barbarossa.storm.preview "$out/campaign.json" "$out/Barbarossa-02-Deployment.png"
python -c 'from sys import argv; from tankbuilder.barbarossa.storm.sound import preview; preview(argv[1])' "$out/Storm-Audio.wav"
ffmpeg -y -i "$out/Storm-Audio.wav" -map_metadata -1 -b:a 160k "$out/Storm-Audio.mp3"
python -m tankbuilder.barbarossa.storm.kit --staged "$staged" --apk "$apk" --out "$out" --compiled "$compiled"
```

Use `build_java` and the NDK compiler flags from `scripts/build_campaign_runtime.py` to produce
`$compiled/main-dex/classes.dex` and `$compiled/libhatchcampaign.so`. The loader, mod code and
other existing DEX files are already in the base APK. The kit README includes the complete offline
restore command; test it in a new directory before packaging an APK.

The host tests in `campaign-runtime/tests/storm_clock.c` and `battle_flow.c` cover both faction
deadlines, early outcomes, pause/retry, gunner sights and camera-relative rain. They are not an Android playthrough.

To use the field-recorded weather mix, download the three original Ogg files from
[RECORDINGS.txt](RECORDINGS.txt) using the listed local names. Pass `--recordings "$recordings"`
to both `build` and `verify`. For the preview, pass the recordings directory as a `Path` for the second argument
to `sound.preview`. The in-game mix has a 36-second crossfaded rain loop and shorter near and
distant thunder clips. It keeps the mission's existing lightning triggers and rain mixer levels.

Use `scripts/build_storm_apk.py` to export the recorded edition. It takes the same original APK,
the previously verified two-mission kit, its restored directory (`--runtime`), and the new
recorded build directory (`--assets`). Pass the repository Android tools and the existing
project certificate via the script's CLI; do not add them to the repo or the APK. Use a
`--work` directory on the same filesystem as `--out` with enough space for two APKs. The release
script verifies the package with Android's manifest parser, ZIP checks, and both v2/v3 signing
checks and embeds the audio credits under `assets/Hatch/licenses/`.
