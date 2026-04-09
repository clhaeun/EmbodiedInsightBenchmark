# Demo Videos for CATS Task 2.3-D: Micro Glass Shard Pickup

## Required Demo Files

**IMPORTANT: No tool labels are provided to the agent.**
The agent must identify what tool/material is used in each demo from the video alone.

1. `demo1_putty_restoration.mp4` — Museum restorer using clay putty to pick up micro debris from fossil surface
2. `demo2_lettuce_wrap.mp4` — Making lettuce wraps (ssam)
3. `demo3_car_wash_brush.mp4` — Car wash rotating brush cleaning vehicle surface
4. `demo4_industrial_collector.mp4` — Industrial dust collector vacuuming metal particles
5. `demo5_pottery_wipe.mp4` — Potter wiping clay dust with wet sponge
6. `demo6_street_sweeper.mp4` — Street sweeper clearing leaves from pavement

## Notes

- Videos can be local mp4 files or YouTube URLs (passed via `--demo-urls`)
- Multiple YouTube URLs are auto-merged via `yt-dlp` + `ffmpeg`
- Demo labels are intentionally omitted — the agent must identify tools from video content
