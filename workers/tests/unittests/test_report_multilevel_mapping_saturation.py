import unittest
from unittest.mock import Mock

from ohsome_quality_analyst.reports.multilevel_mapping_saturation.report import (
    MultilevelMappingSaturation,
)

from .utils import get_geojson_fixture


class TestReportMultilevelMappingSaturation(unittest.TestCase):
    # TODO: Test case for indicator.result undefined
    def test_combine_indicators_mean(self):

        geometry = get_geojson_fixture("heidelberg-altstadt-geometry.geojson")
        report = MultilevelMappingSaturation(geometry)

        # Mock indicator objects with a fixed result value
        for _ in report.indicator_layer:
            indicator = Mock()
            indicator.result = Mock()
            indicator.result.class_ = 1
            indicator.result.html = "foo"
            report.indicators.append(indicator)

        report.combine_indicators()
        report.create_html()

        self.assertIsNotNone(report.result.label)
        self.assertIsNotNone(report.result.description)
        self.assertIsNotNone(report.result.html)
        self.assertEqual(report.result.class_, 1)


if __name__ == "__main__":
    unittest.main()
