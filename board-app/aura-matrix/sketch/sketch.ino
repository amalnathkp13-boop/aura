// Aura LED matrix face — UNO Q M33 side.
//
// This reuses the animation logic from sketch/aura_matrix/aura_matrix.ino
// (radar sweep / aura bloom / alert strobe / fault blink over fb[8][13])
// verbatim, with only the transport swapped: instead of polling Serial for
// "S,<presence>,<motion>,<activity>,<alert>\n" lines, state arrives via the
// arduino-app-cli RouterBridge RPC channel — the Python side (python/main.py)
// calls Bridge.call("state", bytes4) roughly every 0.2s, which invokes the
// state() provider below on a separate Zephyr thread.
//
// Matrix rendering follows the on-board led-matrix-painter example:
// Arduino_LED_Matrix + setGrayscaleBits(3) + matrix.draw(104-byte buffer,
// values 0 or 7).
#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <vector>
#include <math.h>
#include <string.h>
#include <zephyr/kernel.h>

Arduino_LED_Matrix matrix;

const int W = 13, H = 8;
uint8_t fb[H][W];
uint8_t presence = 0, motionF = 0, activity = 0, alertF = 0;
unsigned long lastStateMs = 0;
float sweepX = 0;

// Bridge providers (state()) run on a separate Zephyr thread from loop().
// This mutex protects the shared state (presence/motionF/activity/alertF/
// lastStateMs) and serializes it against loop()'s reads, the same pattern
// the led-matrix-painter example uses around its animation state + draw.
K_MUTEX_DEFINE(state_mtx);

void clearFb() { memset(fb, 0, sizeof(fb)); }

void drawFrame() {
  // Map the logical on/off framebuffer (0/1) to matrix grayscale levels
  // (0..7, since setGrayscaleBits(3) is configured in setup()).
  uint8_t out[H][W];
  for (int y = 0; y < H; y++)
    for (int x = 0; x < W; x++)
      out[y][x] = fb[y][x] ? 7 : 0;
  matrix.draw(&out[0][0]);
}

void radarSweep() {
  clearFb();
  sweepX += 0.35; if (sweepX >= W) sweepX = 0;
  int x = (int)sweepX;
  for (int y = 0; y < H; y++) {
    fb[y][x] = 1;
    if (x > 0) fb[y][x - 1] = (y % 2) ? 1 : 0;  // fading trail
  }
}

void auraBloom() {
  clearFb();
  float r = 1.0f + (activity / 100.0f) * 5.0f;
  float cx = W / 2.0f, cy = H / 2.0f;
  float pulse = motionF ? (0.5f * sinf(millis() / 150.0f)) : 0.0f;
  for (int y = 0; y < H; y++)
    for (int x = 0; x < W; x++) {
      float d = sqrtf((x - cx) * (x - cx) + (y - cy) * (y - cy));
      if (d <= r + pulse) fb[y][x] = 1;
    }
}

void alertStrobe() {
  bool on = (millis() / 125) % 2;
  memset(fb, on ? 1 : 0, sizeof(fb));
}

void faultBlink() {
  clearFb();
  fb[0][0] = (millis() / 500) % 2;
}

void applyState(uint8_t p, uint8_t m, uint8_t a, uint8_t al) {
  presence = p; motionF = m; activity = a; alertF = al;
}

// Bridge provider — invoked on a separate Zephyr thread whenever the Python
// side calls Bridge.call("state", bytes([presence, motion, activity, alert])).
void state(std::vector<uint8_t> v) {
  if (v.size() < 4) return;
  k_mutex_lock(&state_mtx, K_FOREVER);
  applyState(v[0], v[1], v[2], v[3]);
  lastStateMs = millis();
  k_mutex_unlock(&state_mtx);
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);   // accept 0..7 brightness values
  matrix.clear();

  lastStateMs = millis();

  Bridge.begin();
  Bridge.provide("state", state);
}

void loop() {
  k_mutex_lock(&state_mtx, K_FOREVER);
  if (millis() - lastStateMs > 5000) faultBlink();   // no state for >5s
  else if (alertF) alertStrobe();
  else if (presence) auraBloom();
  else radarSweep();
  drawFrame();
  k_mutex_unlock(&state_mtx);

  delay(33);
}
