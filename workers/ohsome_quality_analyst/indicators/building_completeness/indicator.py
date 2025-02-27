import logging
import os
from io import StringIO
from string import Template

import dateutil.parser
import geojson
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
from building_completeness_model import Predictor, Processor
from geojson import Feature, FeatureCollection

import ohsome_quality_analyst.geodatabase.client as db_client
from ohsome_quality_analyst.base.indicator import BaseIndicator
from ohsome_quality_analyst.base.layer import BaseLayer as Layer
from ohsome_quality_analyst.definitions import get_raster_dataset
from ohsome_quality_analyst.ohsome import client as ohsome_client
from ohsome_quality_analyst.raster import client as raster_client
from ohsome_quality_analyst.utils.exceptions import HexCellsNotFoundError


class BuildingCompleteness(BaseIndicator):
    """Building Completeness Indicator

    Predicts the building area of the AOI using a trained Random Forest Regressor.
    The result is a weighted average of the ratios between the building area mapped in
    OSM and the predicted building area of each hex-cell. The weight is the predicted
    building area.

    The input parameters (X or Covariates) to the models are population and population
    density (GHSL GHS-POP), settlement typologies (GHSL SMOD), subnational Human
    Development Index (GDL SHDI) and nightlights (EGO VNL). In particular following
    parameters:
        - shdi: List[float]
        - vnl: List[float]
        - ghs_pop: List[float]
        - ghs_pop_density: List[float]  # [sqkm]
        - water: List[float] = 0.0
        - very_low_density_rural: List[float]= 0.0
        - low_density_rural: List[float] = 0.0
        - rural_cluster: List[float] = 0.0
        - suburban_or_peri_urban: List[float] = 0.0
        - semi_dense_urban_cluster: List[float] = 0.0
        - dense_urban_cluster: List[float] = 0.0
        - urban_centre: List[float] = 0.0

    The spatial resolution of the model are hex-cells (DGGRID ISEA 3H World Resolution
    12). The input AOI is split into hex-cells and the prediction is done for each of
    those. The model is trained on hex-cells in Africa. Therefor the Indicator is
    restricted to input AOI within the bounding box of Africa.

    The training data and code of the model training are accessible at:
    https://gitlab.gistools.geog.uni-heidelberg.de/giscience/big-data/ohsome/ml-models/building-completeness-model
    """

    def __init__(
        self,
        layer: Layer,
        feature: Feature,
    ) -> None:
        super().__init__(
            layer=layer,
            feature=feature,
        )
        self.model_name: str = "Random Forest Regressor"
        # Lists of elements per hexagonal cell
        self.building_area_osm: list = []
        self.building_area_prediction: list = []
        self.covariates: dict = {}
        self.hex_cell_geohash: list = []

    @classmethod
    def threshhold_green(cls):
        """Above or equal to this value label should be green."""
        return 0.8

    @classmethod
    def threshhold_yellow(cls):
        """Above or equal to this value label should be yellow."""
        return 0.2

    async def preprocess(self) -> None:
        # Get hex-cells
        hex_cells: FeatureCollection = await get_hex_cells(self.feature)
        self.hex_cell_geohash = [feature.id for feature in hex_cells.features]
        # Get OSM data
        query_results = await ohsome_client.query(
            self.layer,
            hex_cells,
            group_by_boundary=True,
        )
        # Extract OSM data
        self.result.timestamp_osm = dateutil.parser.isoparse(
            query_results["groupByResult"][0]["result"][0]["timestamp"]
        )
        self.building_area_osm = [
            item["result"][0]["value"] for item in query_results["groupByResult"]
        ]
        # Get covariates (input parameters or X)
        ghs_pop = raster_client.get_zonal_stats(
            hex_cells,
            get_raster_dataset("GHS_POP_R2019A"),
            stats=["sum"],
        )
        vnl = raster_client.get_zonal_stats(
            hex_cells,
            get_raster_dataset("VNL"),
            stats=["sum"],
        )
        self.covariates["shdi"] = await get_shdi(hex_cells)
        self.covariates["vnl"] = [i["sum"] for i in vnl]
        self.covariates["ghs_pop"] = [i["sum"] or 0 for i in ghs_pop]
        self.covariates["ghs_pop_density"] = [
            pop / cell.properties["area"]
            for pop, cell in zip(self.covariates["ghs_pop"], hex_cells["features"])
        ]
        self.covariates.update(get_smod_class_share(hex_cells))

    def calculate(self) -> None:
        if len(self.covariates.keys()) != 12:
            logging.info("Not all covariates are present. Skipping calculation.")
            return
        # Predict
        X = Processor.preprocess(**self.covariates)  # noqa: N806
        y = Predictor.predict(X)
        self.building_area_prediction = [0 if v < 0 else v for v in y]
        # Compare
        self.completeness_ratio = [
            osm / prediction
            for osm, prediction in zip(
                self.building_area_osm, self.building_area_prediction
            )
        ]
        # Weighed average of ratio
        self.result.value = np.average(
            self.completeness_ratio,
            weights=self.building_area_prediction,
        )
        if self.result.value >= self.threshhold_green():
            self.result.class_ = 5
        elif self.result.value >= self.threshhold_yellow():
            self.result.class_ = 3
        elif 0.0 <= self.result.value < self.threshhold_yellow():
            self.result.class_ = 1
        else:
            raise ValueError(
                "Result value (percentage mapped) is an unexpected value: {}".format(
                    self.result.value
                )
            )
        description = Template(self.metadata.result_description).substitute(
            building_area_osm=round(sum(self.building_area_osm), 2),
            building_area_prediction=round(sum(self.building_area_prediction), 2),
            completeness_ratio=round(self.result.value * 100, 2),
        )
        self.result.description = (
            description + self.metadata.label_description[self.result.label]
        )

    def create_figure(self) -> None:
        if self.result.label == "undefined":
            logging.info("Result is undefined. Skipping figure creation.")
            return
        px = 1 / plt.rcParams["figure.dpi"]  # Pixel in inches
        figsize = (400 * px, 400 * px)
        fig = plt.figure(figsize=figsize, tight_layout=True)
        ax = fig.add_subplot()
        ax.set_title("Building Completeness")
        ax.set_xlabel("Completeness Ratio [%]")
        ax.set_ylabel("Distribution Density [%]")
        ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(10))
        _, _, patches = ax.hist(
            [i for i in self.completeness_ratio],
            bins=15,  # to account for overprediction (>100% completeness)
            range=(0, 1.5),
            density=True,
            weights=self.building_area_prediction,
            edgecolor="black",
        )
        for patch in patches:
            x = round(abs(patch.get_x()), 2)
            if x >= self.threshhold_green():
                patch.set_facecolor("green")
            elif x >= self.threshhold_yellow():
                patch.set_facecolor("yellow")
            elif 0.0 <= x < self.threshhold_yellow():
                patch.set_facecolor("red")
            else:
                patch.set_facecolor("grey")
        plt.axvline(
            x=self.result.value,
            linestyle=":",
            color="black",
            label="Weighted Average: {0}%".format(int(self.result.value * 100)),
        )
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.45))
        # has to be executed after "major formatter setting"
        plt.xlim(0, 1.5)
        plt.ylim(0, 10)
        img_data = StringIO()
        plt.savefig(img_data, format="svg", bbox_inches="tight")
        self.result.svg = img_data.getvalue()
        plt.close("all")


def get_smod_class_share(featurecollection: FeatureCollection) -> dict:
    """Get the share of GHSL SMOD L2 classes for each feature.

    Returns:
        list: List of dictionaries where the keys are the category names and the values
            are the share of the class (0, 1).
    """
    category_map = {
        30: "urban_centre",
        23: "dense_urban_cluster",
        22: "semi_dense_urban_cluster",
        21: "suburban_or_peri_urban",
        13: "rural_cluster",
        12: "low_density_rural",
        11: "very_low_density_rural",
        10: "water",
    }
    # Get a dict containing unique raster values as keys and pixel counts as values
    class_count = raster_client.get_zonal_stats(
        featurecollection,
        get_raster_dataset("GHS_SMOD_R2019A"),
        categorical=True,
        category_map=category_map,
    )
    pixel_count = raster_client.get_zonal_stats(
        featurecollection,
        get_raster_dataset("GHS_SMOD_R2019A"),
        stats=["count"],
    )
    pixel_count = [i["count"] for i in pixel_count]
    shares = {}
    for category in category_map.values():
        shares[category] = [
            c.get(category, 0) / p for c, p in zip(class_count, pixel_count)
        ]
    return shares


async def get_hex_cells(feature: Feature) -> FeatureCollection:
    """Select hex-cells which are intersecting with features of a FeatureCollection.

    Raises:
        HexCellsNotFoundError
    """
    file_path = os.path.join(
        os.path.dirname(
            os.path.abspath(__file__),
        ),
        "select_hex_cells.sql",
    )
    with open(file_path, "r") as file:
        query = file.read()
    async with db_client.get_connection() as conn:
        record = await conn.fetchrow(query, str(feature.geometry))
    feature_collection = geojson.loads(record[0])
    if feature_collection["features"] is None:
        raise HexCellsNotFoundError
    return feature_collection


async def get_shdi(featurecollection: FeatureCollection) -> list:
    """Get SHDI values for each feature.

    If feature does not intersect with the SHDI geometry take the mean of all present
    SHDI values.
    """
    records = await db_client.get_shdi(featurecollection)
    if len(records) == len(featurecollection):
        return [r["shdi"] for r in records]
    else:
        # Not every feature has a SHDI value
        default = np.mean([r["shdi"] for r in records])  # Default value
        shdi = [default for _ in featurecollection.features]  # List of default values
        for r in records:
            shdi[r["rownumber"] - 1] = r["shdi"]  # Overwrite default values
        return shdi
