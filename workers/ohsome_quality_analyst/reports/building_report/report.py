from geojson import Feature

from ohsome_quality_analyst.base.report import BaseReport, IndicatorLayer


class BuildingReport(BaseReport):
    def __init__(
        self,
        feature: Feature,
        blocking_red: bool = None,
        blocking_undefined: bool = None,
    ):
        super().__init__(
            indicator_layer=(
                IndicatorLayer("MappingSaturation", "building_count"),
                IndicatorLayer("Currentness", "building_count"),
                IndicatorLayer("TagsRatio", "building_count"),
                IndicatorLayer("BuildingCompleteness", "building_area"),
            ),
            feature=feature,
            blocking_red=blocking_red,
            blocking_undefined=blocking_undefined,
        )

    def combine_indicators(self) -> None:
        super().combine_indicators()
