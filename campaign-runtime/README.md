# Offline campaign runtime (Attack on Tank 5.1.0)

The title buttons activate one named request. The companion uses the already running Unity player's Android Looper and the project's scripting adapter to set and read back game mode, player/hostile nationality, unit slot, and stage on the live manager, then loads scene 22/23 (Gates of Hell) or 24/25 (Stormbreak). Selecting a side never changes saved campaign progression. Each scene contains its own inactive factory and an active-self source player, independent of the battlefield placeholder disabled by the stock generator.

In a local campaign, scaled time bounds repeated panic to 2.5 s and a temporary gunner interruption to 5 s, with a two-second recovery window. HP, crew deaths, track repair, towed vehicles, destroyed vehicles and other modes retain their original rules. Combat captions and radio messages are noninteractive. The original core native library, voice pack, ballistics and suspension implementation are delivered unchanged. T-26 belts keep the authored 80-shoe vertex layout and per-instance writable buffers.

The mission's serialized stock TimedEvent components activate five German reserves after 90 s and two Soviet T-34s after 150 s. The enemy aircraft uses the original field's intact aircraft controller, ordnance, affiliation and sighting components: Ju 87 for the Soviet perspective (78 s), Il-2 for the German perspective (135 s). The final objective activates with the T-34s to prevent the first wave from incorrectly ending the battle. Pause, replay and faction switching reuse per-scene timers. The APK requires the Java classes, native companion and updated core module from the same release. The Android runtime build is in `scripts/build_campaign_runtime.py`.


The cumulative APK registers the F and the Luchs with the same held-fire and magazine settings. In the German mission the stock fire artwork is a child of a zero-area visibility wrapper. Its serialized EventTrigger latches pointer down, releases on up/exit/cancel, and has no fire-on-release callback. The local player's ten-shot clock is advanced by a confirmed main-gun launch. The baked and factory player and the resource prefab each hold 12 independently owned projectiles. AI cannot reset the player's counter.

The original capture trigger is active from the beginning through a temporary capture-only rule. At the second wave a stock timer replaces it with the complete native rule. Stock GameControl and GameUiManager own the result UI. Duplicates are suppressed per controller instance; a destroyed player can reach the result screen even before the second wave.

Only the extra campaign's green dot uses the pool's fpTrf, the chambered shell, the owning player's initialized projectile speed when observable, fixed physics ticks and actual Android render-surface bounds. The marker is nominal and does not remove the game's spread.

To build on the last cumulative APK and kit, run `scripts/prepare_battleflow.py` and then `scripts/build_gameplay_refit.py` with the repository SDK/NDK and original project certificate. The integration overlay preserves the stock compressed blocks and checks every live Unity member after writing.

The existing projectile module filters colliders under the live shooter's hierarchy root. The green indicator uses that same runtime root, even if it differs from the serialized player's transform (the two authored rosters start under Campaign Units). No original projectile damage/collision callbacks are replaced.


Stormbreak uses the same stock Field 1 scenario slot in two new scene assets. Campaign entry,
retry and the first mission's Next button all restore that slot and the selected nation/vehicle
before loading. Its two native reserve timers leave all tanks visible and damageable from the
start. A scaled 780-second clock calls the stock victory/defeat routines, including the TimeLimit
result reason. Only these two scenes run camera-relative rain and their occasional forked
lightning with delayed thunder. See [the scene builder](../tankbuilder/barbarossa/storm/README.md).
