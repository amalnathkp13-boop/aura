// Aura LED matrix face — UNO Q M33 side.
// ADAPT LINE A: include the matrix library exactly as the on-board App Lab matrix example does.
#include <Arduino_LED_Matrix.h>   // ADAPT-A if the example differs
ArduinoLEDMatrix matrix;          // ADAPT-A

const int W = 13, H = 8;
uint8_t fb[H][W];
uint8_t presence = 0, motionF = 0, activity = 0, alertF = 0;
unsigned long lastSerialMs = 0;
float sweepX = 0;

void drawFrame() {
  // ADAPT LINE B: this is the only draw call — replace with the example's frame-render call.
  matrix.renderBitmap(fb, H, W); // ADAPT-B
}

void clearFb() { memset(fb, 0, sizeof(fb)); }

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

void pollSerial() {
  static char buf[32]; static int n = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      buf[n] = 0; n = 0;
      int p, m, a, al;
      if (sscanf(buf, "S,%d,%d,%d,%d", &p, &m, &a, &al) == 4) {
        applyState(p, m, a, al);
        lastSerialMs = millis();
      }
    } else if (n < 30) buf[n++] = c;
  }
}

void setup() {
  Serial.begin(115200);
  matrix.begin();               // ADAPT-A if the example differs
  lastSerialMs = millis();
}

void loop() {
  pollSerial();
  if (millis() - lastSerialMs > 5000) faultBlink();
  else if (alertF) alertStrobe();
  else if (presence) auraBloom();
  else radarSweep();
  drawFrame();
  delay(33);
}
