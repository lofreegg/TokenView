import unittest


class LayoutTests(unittest.TestCase):
    def test_expanding_does_not_inherit_capsule_width(self):
        from tokenview.layout import capsule_width, panel_height, row_rects
        self.assertLess(capsule_width(80, [60, 60], False), 420)
        self.assertEqual(capsule_width(80, [60, 60], True), 486)
        self.assertGreater(panel_height(2, False, 900), 320)
        name, first, second, trash = row_rects(486)
        self.assertLess(name[0] + name[2], first[0])
        self.assertLessEqual(first[0] + first[2], second[0])
        self.assertLess(second[0] + second[2], trash[0])

    def test_many_accounts_fit_in_screen_and_remain_scrollable(self):
        from tokenview.layout import panel_height, visible_rows
        height = panel_height(30, True, 640)
        self.assertLessEqual(height, 640)
        rows, start = visible_rows(30, height, True, 29)
        self.assertGreaterEqual(rows, 1)
        self.assertLess(start, 30)
        self.assertEqual(start + rows, 30)

    def test_compact_account_rows_do_not_overlap_footer(self):
        from tokenview.layout import panel_height, visible_rows
        for feed in (True,False):
            height=panel_height(2,feed,900)
            rows,_=visible_rows(2,height,feed,0)
            last_bottom=164+(rows-1)*142+130
            next_top=height-69
            self.assertLessEqual(last_bottom+8,next_top)


if __name__ == '__main__':
    unittest.main()
