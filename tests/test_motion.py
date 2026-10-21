import unittest


class MotionTests(unittest.TestCase):
    def test_leaving_closes_promptly_and_reentry_cancels_close(self):
        from tokenview.interaction import LeaveGate
        gate=LeaveGate()
        self.assertFalse(gate.close_due(False,1.0))
        self.assertTrue(gate.close_due(False,1.16))
        self.assertFalse(gate.close_due(True,1.17))
        self.assertFalse(gate.close_due(False,1.18))

    def test_pin_holds_but_does_not_leave_stale_timeout_on_release(self):
        from tokenview.interaction import LeaveGate
        gate=LeaveGate()
        self.assertFalse(gate.close_due(False,1,True))
        self.assertFalse(gate.close_due(False,10,True))
        self.assertFalse(gate.close_due(False,11,False))
        self.assertTrue(gate.close_due(False,11.16,False))

    def test_bridge_between_capsule_and_popup_keeps_hover_alive(self):
        from tokenview.interaction import pointer_inside
        capsule=(40,20,300,40)
        panel=(40,68,486,400)
        self.assertTrue(pointer_inside(90,64,capsule,panel))
        self.assertFalse(pointer_inside(90,12,capsule,panel))
        self.assertFalse(pointer_inside(540,64,capsule,panel))

    def test_ring_sweep_uses_real_quota_not_animation_phase(self):
        from tokenview.visual import ring_sweep,pulse_position
        self.assertEqual(ring_sweep(25),90)
        self.assertEqual(ring_sweep(0),0)
        self.assertEqual(ring_sweep(None),0)
        self.assertLess(pulse_position(0.1,100),pulse_position(0.5,100))
