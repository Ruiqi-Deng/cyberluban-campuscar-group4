import unittest

from protocol_parsers import parse_esp32_line, parse_nmea_gga


class ParserTests(unittest.TestCase):
    def test_esp32(self):
        self.assertEqual(
            parse_esp32_line("POS,0,0,1,250,600,99000"),
            {"lock_status": 1, "temperature": 25.0, "humidity": 60.0, "battery": 99.0},
        )

    def test_standard_gga(self):
        lat, lon, quality = parse_nmea_gga(
            "$GNGGA,060053.00,2253.53800611,N,11328.56206546,E,4,23,0.6,5.0,M,0,M,,*00"
        )
        self.assertAlmostEqual(lat, 22.8923001018, places=8)
        self.assertAlmostEqual(lon, 113.4760344243, places=8)
        self.assertEqual(quality, 4)

    def test_nonstandard_gga_without_decimal(self):
        lat, lon, quality = parse_nmea_gga(
            "$GNGGA,060053.00,225353800611,N,1132856206546,E,4,23,0.6,5.0,M,0,M,,*00"
        )
        self.assertAlmostEqual(lat, 22.8923001018, places=8)
        self.assertAlmostEqual(lon, 113.4760344243, places=8)
        self.assertEqual(quality, 4)


if __name__ == "__main__":
    unittest.main()
