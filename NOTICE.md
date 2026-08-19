# NOTICE

## RuView (MIT)

`aura/brain/ruview/features_rv.py` and `aura/brain/ruview/classifier_rv.py` are ports of
code from the RuView project:

- Repository: https://github.com/ruvnet/RuView
- Commit: 81cc241b9ebf8ccfb7cffd8e2e086e16c81f8a22 (2026-04-26)
- Files: archive/v1/src/sensing/feature_extractor.py, archive/v1/src/sensing/classifier.py
- License: MIT

Local modifications:
- numpy-only: `scipy.fft` replaced with `np.fft` (identical rFFT math); skewness/kurtosis
  removed (never read by the classifier); `scipy.stats` dependency removed.
- The `WifiSample`-based `extract()` path and window trimming were removed — Aura's brain
  owns windowing and feeds plain arrays via `extract_from_array()`.
- Logging and upstream package imports removed.
- `classifier.py` rules and confidence model kept verbatim; per-link thresholds are
  injected by Aura's calibration; multi-link fusion around it is Aura-original.
- Upstream's `rssi_collector.py` is NOT used — Aura's ear daemon owns all radio access.

MIT License

Copyright (c) RuView contributors (https://github.com/ruvnet/RuView)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
