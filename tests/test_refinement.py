import unittest


class CapsuleSpacingTests(unittest.TestCase):
    def test_collapsed_capsule_has_no_model_or_account_name(self):
        from tokenview.ui import Desktop
        from types import SimpleNamespace
        for product in ['codex', 'antigravity', 'deepseek']:
            ui = SimpleNamespace(expanded=False,store=SimpleNamespace(selected_product=product),
                                 current=lambda: None,accounts=lambda: [])
            self.assertEqual(Desktop.capsule_name(ui),'')
    def test_antigravity_capsule_does_not_include_account(self):
        from tokenview.ui import Desktop
        from types import SimpleNamespace
        ui = SimpleNamespace(store=SimpleNamespace(selected_product='antigravity'),
                             current=lambda: SimpleNamespace(name='private@example.com'),
                             accounts=lambda: [1, 2])
        self.assertEqual(Desktop.capsule_name(ui), 'Antigravity')

    def test_capsule_labels_share_actual_ink_center(self):
        from tokenview.painting import Painter
        from System.Drawing import Bitmap, Graphics, Color
        painter = Painter()
        centers = []
        for label in ['5H', '周']:
            bitmap = Bitmap(40, 40)
            graphics = Graphics.FromImage(bitmap)
            graphics.Clear(Color.White)
            painter.capsule_label(graphics, label, 0, 0, 40, 40, '#18263E')
            rows = [y for y in range(40) if any(bitmap.GetPixel(x,y).R < 150 for x in range(40))]
            centers.append((min(rows)+max(rows))/2)
            graphics.Dispose()
            bitmap.Dispose()
        painter.dispose()
        self.assertLessEqual(abs(centers[0]-centers[1]), 0.5)
    def test_secondary_text_is_readable_on_light_cards(self):
        from tokenview.painting import MUTED
        from tokenview.visual import contrast_ratio
        self.assertGreaterEqual(contrast_ratio(MUTED, '#F4F8FC'), 4.5)

    def test_expanded_metrics_do_not_leave_an_oversized_leading_gap(self):
        from tokenview.visual import capsule_metric_positions
        compact = capsule_metric_positions(67, 300, False)
        expanded = capsule_metric_positions(67, 486, True)
        self.assertLessEqual(expanded[0] - compact[0], 10)

    def test_host_palette_rejects_text_outliers_and_keeps_dark_text_legible(self):
        from tokenview.visual import host_palette, contrast_ratio
        light = host_palette([(249, 246, 242)] * 6 + [(30, 30, 30)])
        dark = host_palette([(28, 32, 40)] * 6 + [(240, 240, 240)])
        self.assertGreater(contrast_ratio(light['background'], light['muted']), 4.5)
        self.assertGreater(contrast_ratio(dark['background'], dark['muted']), 4.5)
        self.assertLess(contrast_ratio(light['background'], '#F9F6F2'), 1.1)
        self.assertGreater(contrast_ratio(dark['background'], light['background']), 10)

    def test_midtone_hosts_keep_labels_and_provider_ring_visible(self):
        from tokenview.visual import host_palette, contrast_ratio, capsule_accent
        for rgb in [(130, 130, 130), (82, 115, 232), (35, 139, 236)]:
            palette = host_palette([rgb] * 5)
            self.assertGreaterEqual(contrast_ratio(palette['background'], palette['ink']), 4.5)
            self.assertGreaterEqual(contrast_ratio(palette['background'], palette['muted']), 4.5)
            accent = capsule_accent(palette['background'], '#5273E8')
            self.assertGreaterEqual(contrast_ratio(palette['background'], accent), 3)

    def test_expansion_shifts_metrics_right_without_overlapping_brand(self):
        from tokenview.visual import capsule_metric_positions
        compact = capsule_metric_positions(67, 300, False)
        expanded = capsule_metric_positions(67, 486, True)
        self.assertGreater(expanded[0], compact[0])
        self.assertGreater(expanded[1] - expanded[0], compact[1] - compact[0])
        self.assertLessEqual(expanded[1] + 62, 486 - 144)
        self.assertLess(compact[1] + 62, 300 - 22)


if __name__ == '__main__':
    unittest.main()
