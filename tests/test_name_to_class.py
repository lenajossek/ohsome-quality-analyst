import unittest

from ohsome_quality_tool.indicators.ghs_pop_comparison.indicator import GhsPopComparison

# from ohsome_quality_tool.reports.simple_report.report import SimpleReport
from ohsome_quality_tool.utils.definitions import load_indicator_metadata
from ohsome_quality_tool.utils.helper import name_to_class


class TestNameToClass(unittest.TestCase):
    def setUp(self):
        self.indicators = load_indicator_metadata()

    def test(self):
        self.assertIs(
            name_to_class(class_type="indicator", name="GhsPopComparison"),
            GhsPopComparison,
        )
        # TODO
        # self.assertIs(
        #     name_to_class(class_type="report", name="SimpleReport"),
        #     SimpleReport,
        # )

    def test_all_indicators(self):
        for indicator in self.indicators.keys():
            self.assertIsNotNone(
                name_to_class(class_type="indicator", name="GhsPopComparison")
            )


if __name__ == "__main__":
    unittest.main()
