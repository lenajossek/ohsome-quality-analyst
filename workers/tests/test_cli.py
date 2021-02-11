"""
Testing Click Applications:
https://click.palletsprojects.com/en/7.x/testing/?highlight=testing
"""

import os
import unittest

from click.testing import CliRunner

from ohsome_quality_analyst.cli import cli


class TestCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.infile = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "fixtures",
            "heidelberg_altstadt.geojson",
        )

    def testCli(self):
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0

    def testListIndicators(self):
        result = self.runner.invoke(cli, ["list-indicators"])
        assert result.exit_code == 0

    def testListReports(self):
        result = self.runner.invoke(cli, ["list-reports"])
        assert result.exit_code == 0

    def testListLayers(self):
        result = self.runner.invoke(cli, ["list-layers"])
        assert result.exit_code == 0

    def testListDatasets(self):
        result = self.runner.invoke(cli, ["list-datasets"])
        assert result.exit_code == 0

    def testCreateIndicator(self):
        result = self.runner.invoke(
            cli,
            [
                "create-indicator",
                "-i",
                "GhsPopComparison",
                "-l",
                "building_count",
                "-d",
                "test_regions",
                "-f",
                "3",
            ],
        )
        assert result.exit_code == 0

    def testCreateReport(self):
        result = self.runner.invoke(
            cli,
            ["create-report", "-r", "SimpleReport", "-d", "test_regions", "-f", "3"],
        )
        assert result.exit_code == 0

    def testCreateAllIndicators(self):
        result = self.runner.invoke(
            cli,
            ["create-all-indicators", "-d", "test_regions"],
            input="N\n",
        )
        assert result.exit_code == 1


if __name__ == "__main__":
    unittest.main()
