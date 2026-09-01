# Day/Night Fix Report — Real-Time Earth Lighting

## Summary
Fixed the issue where the Earth's day/night would "drift" and places that
should be in darkness would light up after the globe rotated for a while.
Now the day/night terminator is permanently anchored to real geographic
coordinates and driven by the real UTC time, exactly as the user requested.

## What was failing

### Root cause
The globe auto-rotates for visual effect at `autoRotateSpeed = 0.05 rad/s`,
which is about **2.9° per second** — a full spin in ~2 minutes.

The real Earth rotates only **15° per hour** (~0.0042°/s).

So the demo globe was spinning roughly **700× faster than reality**.

The Sun direction was held **fixed in world space** (an inertial, non-moving
sun). In three.js the shaders compute world-space surface normals and dot them
with that fixed sun direction, so the day/night boundary (terminator) stayed
fixed in *space* while the super-fast globe spun continents through it.

Net effect: as the globe rotated, continents were whipped through the lit zone
unrealistically fast, so a place that is genuinely in night (e.g. India during
real nighttime) kept swinging back into "daylight" every couple of minutes.
That was the visible bug: *"the place where there should be night becomes
bright."*

The initial state looked correct only because at yaw=0 the sun vector happened
to line up with the texture; once rotation accumulated, the mismatch appeared.

## The fix (geo-anchored day/night)
File: `src/earth/EarthScene.tsx`

- Kept the real-UTC subsolar direction as the **geographic** (texture-space)
  sun direction (`geoSunRef`), computed from the ticking `now` clock.
- Every frame, we rotate that sun direction **together with the globe's yaw**
  before handing it to the shaders:

  ```
  sun = rotateY(geoSun, globeYaw)
  ```

  Because the shader normals are also rotated by the same `modelMatrix`, the
  two rotations cancel out in the lighting dot-product, so the day/night
  pattern becomes **fixed to the texture/geography** — it no longer sweeps
  across continents regardless of how fast the globe spins.

This keeps the pretty auto-rotating globe AND makes the day/night permanently
correct. The same sun is fed to the Earth surface, the clouds, and the
atmosphere rim-glow, so all three stay in sync.

## Verification (deterministic, against real data)
A CPU math check sampling real city coordinates (New Delhi, Mumbai, London,
New York, Tokyo, Sydney, Rio, Kenya) at multiple globe yaws:

| Check | Result |
|-------|--------|
| Day/night classification identical across all globe yaws | **PASS** |
| Geography correct at actual time (UTC ~20:07, subsolar 8.9°N 123°W) | **PASS** |
| No world-space sun sweep during rotation | **PASS** |

At that moment the model correctly shows: New York = day, while New Delhi
(1:37 AM) / Mumbai / London / Tokyo / Kenya = night — matching the real world.

- `tsc -b` — clean
- `npm run lint` — clean (only pre-existing unrelated warnings)
- `npm run build` — clean
- Headless browser render — no shader/GL/JS errors, canvas renders

## Files changed
- `src/earth/EarthScene.tsx` — geo-anchored sun rotation (the fix)
