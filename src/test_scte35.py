# HLS tools.
# Copyright (C) 2021, MediaMonks B.V. All rights reserved.

import scte35
import inspect
import unittest

class SCTE35TestCase(unittest.TestCase):

	def test_basics(self):
		self.assertEqual(
			"FC001C00000000000000FFF00F05000004D200C080055D4A800A1E00000000342F0441",
			scte35.splice_info_with_splice_insert(1234, True, 1000)
		)

	def test_break(self):
		self.assertEqual(
			"FC002100000000000000FFF01405000004D200E080055D4A8000002932E00A1E000000001798AE87",
			scte35.splice_info_with_splice_insert(1234, True, 1000, 30, auto_return = False)
		)
		self.assertEqual(
			"FC002100000000000000FFF01405000004D200E080055D4A8080002932E00A1E0000000060799B18",
			scte35.splice_info_with_splice_insert(1234, True, 1000, 30, auto_return = True)
		)

if __name__ == '__main__':
	unittest.main()
