from aura.brain.ruview.classifier_rv import PresenceClassifier, MotionLevel
from aura.brain.ruview.features_rv import RssiFeatures

def _feat(variance, motion=0.0, breathing=0.0, cps=0):
    return RssiFeatures(variance=variance, motion_band_power=motion,
                        breathing_band_power=breathing, n_change_points=cps)

def test_absent_below_variance_threshold():
    r = PresenceClassifier(0.5, 0.1).classify(_feat(0.1))
    assert r.motion_level == MotionLevel.ABSENT and not r.presence_detected

def test_active_needs_variance_and_motion_energy():
    r = PresenceClassifier(0.5, 0.1).classify(_feat(2.0, motion=0.5))
    assert r.motion_level == MotionLevel.ACTIVE and r.presence_detected

def test_present_still_high_variance_low_motion():
    r = PresenceClassifier(0.5, 0.1).classify(_feat(2.0, motion=0.01, breathing=0.2))
    assert r.motion_level == MotionLevel.PRESENT_STILL and r.presence_detected

def test_confidence_unit_interval_and_agreement():
    clf = PresenceClassifier(0.5, 0.1)
    alone = clf.classify(_feat(2.0, motion=0.5))
    peer = clf.classify(_feat(1.5, motion=0.4))
    agreed = clf.classify(_feat(2.0, motion=0.5), other_receiver_results=[peer])
    disagreed = clf.classify(_feat(2.0, motion=0.5),
                             other_receiver_results=[clf.classify(_feat(0.0))])
    assert 0.0 <= alone.confidence <= 1.0
    assert agreed.confidence >= disagreed.confidence
