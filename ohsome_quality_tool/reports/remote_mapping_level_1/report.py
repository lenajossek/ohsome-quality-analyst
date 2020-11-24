from geojson import FeatureCollection

from ohsome_quality_tool.base.report import BaseReport
from ohsome_quality_tool.utils.definitions import Indicators, logger
from ohsome_quality_tool.utils.layers import LEVEL_1_LAYERS


class Report(BaseReport):
    """The remote mapping level 1 Report."""

    name = "REMOTE_MAPPING_LEVEL_1"
    # TODO: check if this structure is good
    #   maybe we want to have an indicator for last_edit
    #   and pass the objects as a filter instead
    #   then the definition of which specific saturation to compute
    #   would be passed here in the report
    indicators = [
        (Indicators.GHSPOP_COMPARISON, LEVEL_1_LAYERS),
        (Indicators.GUF_COMPARISON, LEVEL_1_LAYERS),
        (Indicators.MAPPING_SATURATION, LEVEL_1_LAYERS),
        (Indicators.LAST_EDIT, LEVEL_1_LAYERS),
    ]

    def __init__(
        self,
        dynamic: bool,
        bpolys: FeatureCollection = None,
        dataset: str = None,
        feature_id: int = None,
    ) -> None:
        super().__init__(
            dynamic=dynamic, bpolys=bpolys, dataset=dataset, feature_id=feature_id
        )

    def combine_indicators(self):
        """Combine the individual scores per indicator."""
        logger.info(f"combine indicators for {self.name} report.")
