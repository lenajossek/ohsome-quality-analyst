import json
import logging
from io import StringIO
from string import Template

import matplotlib.pyplot as plt
import numpy as np
from asyncpg import Record
from geojson import FeatureCollection

from ohsome_quality_analyst.base.indicator import BaseIndicator
from ohsome_quality_analyst.geodatabase import client as db_client
from ohsome_quality_analyst.ohsome import client as ohsome_client


class GhsPopComparisonRoads(BaseIndicator):
    """Set number of features and population into perspective."""

    def __init__(
        self,
        layer_name: str,
        bpolys: FeatureCollection = None,
    ) -> None:
        super().__init__(
            layer_name=layer_name,
            bpolys=bpolys,
        )
        # Those attributes will be set during lifecycle of the object.
        self.pop_count = None
        self.area = None
        self.pop_count_per_sqkm = None
        self.feature_length = None
        self.feature_length_per_sqkm = None
        self.feature_length_per_pop = None

    # threshould values found by checking population density for good
    # test-regions and look what values for road length per people
    # are in these areas
    def greenThresholdFunction(self, pop_per_sqkm) -> list:
        """
        Returns minimum and maximum road length meter per habitant,
        which could be a good value with regard to specific population
        density.
        """
        # define green threshould by population density differently
        if pop_per_sqkm >= 2500:
            return [0.0004, 0.0035]
        elif 500 <= pop_per_sqkm < 2500:
            return [0.0036, 0.0050]
        elif 1 <= pop_per_sqkm < 500:
            return [0.0051, 0.1000]
        elif pop_per_sqkm < 1:
            return [0.1010, 5.0000]

    def yellowThresholdFunction(self, pop_per_sqkm) -> list:
        # define yellow threshould by population density
        # could mean that there are too less roads mapped
        if pop_per_sqkm >= 2500:
            return [0.0001, 0.00039]
        elif pop_per_sqkm >= 500 < 2500:
            return [0.0001, 0.0035]
        elif pop_per_sqkm < 500:
            return [0.0001, 0.0050]
        elif pop_per_sqkm < 1:
            return [0.0001, 0.1000]

    async def preprocess(self) -> bool:
        pop_count, area = await self.get_zonal_stats_population(bpolys=self.bpolys)

        if pop_count is None:
            pop_count = 0
        self.area = area
        self.pop_count = pop_count

        query_results = await ohsome_client.query(
            layer=self.layer, bpolys=json.dumps(self.bpolys)
        )
        if query_results is None:
            return False
        # results in meter, we need km
        self.feature_length = query_results["result"][0]["value"] / 1000
        self.feature_length_per_sqkm = self.feature_length / self.area
        self.pop_count_per_sqkm = self.pop_count / self.area
        self.feature_length_per_pop = self.feature_length / self.pop_count
        return True

    def calculate(self) -> bool:
        description = Template(self.metadata.result_description).substitute(
            pop_count=round(self.pop_count),
            area=round(self.area, 1),
            pop_count_per_sqkm=round(self.pop_count_per_sqkm, 1),
            feature_length_per_sqkm=round(self.feature_length_per_sqkm, 1),
        )

        min_pop_density_green = self.greenThresholdFunction(self.pop_count_per_sqkm)[0]
        max_pop_density_green = self.greenThresholdFunction(self.pop_count_per_sqkm)[1]
        min_pop_density_yellow = self.yellowThresholdFunction(self.pop_count_per_sqkm)[
            0
        ]
        max_pop_density_yellow = self.yellowThresholdFunction(self.pop_count_per_sqkm)[
            1
        ]

        if self.pop_count_per_sqkm == 0:
            return False
        # road length per habitant is conform with green values or even higher
        elif (
            max_pop_density_green > self.feature_length_per_pop > min_pop_density_green
            or self.feature_length_per_pop >= max_pop_density_green
        ):
            self.result.value = 1.0
            self.result.description = (
                description + self.metadata.label_description["green"]
            )
            self.result.label = "green"
        # road length per habitant is conform with yellow values, we assume
        # there could be more roads mapped
        elif (
            max_pop_density_yellow
            > self.feature_length_per_pop
            > min_pop_density_yellow
        ):
            self.result.value = 0.5
            self.result.description = (
                description + self.metadata.label_description["yellow"]
            )
            self.result.label = "yellow"
        # road length per habitant is not conform, none or too less roads
        elif (
            self.feature_length == 0
            or self.feature_length_per_pop <= min_pop_density_yellow
        ):
            self.result.value = 0.0
            self.result.description = (
                description + self.metadata.label_description["red"]
            )
            self.result.label = "red"

        return True

    def create_figure(self) -> bool:
        if self.result.label == "undefined":
            logging.info("Skipping figure creation.")
            return

        px = 1 / plt.rcParams["figure.dpi"]  # Pixel in inches
        figsize = (400 * px, 400 * px)
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot()

        ax.set_title("Road length per people against \npeople per $km^2$")
        ax.set_xlabel("Population Density [$1/km^2$]")
        ax.set_ylabel("Road length per people [$km/km^2$]")

        # Set x max value based on area
        if self.pop_count_per_sqkm < 100:
            max_area = 10
        else:
            max_area = round(self.pop_count_per_sqkm * 2 / 10) * 10
        x = np.linspace(0, max_area, 2)
        # get minimum threshould value for green and yellow
        y1a = self.greenThresholdFunction(self.pop_count_per_sqkm)[0]
        y2a = self.yellowThresholdFunction(self.pop_count_per_sqkm)[0]
        # Plot thresholds as line.
        y1 = [y1a, y1a]
        y2 = [y2a, y2a]
        line = ax.plot(
            x,
            y1,
            color="black",
            label="Threshold A",
        )
        plt.setp(line, linestyle="--")

        line = ax.plot(
            x,
            y2,
            color="black",
            label="Threshold B",
        )
        plt.setp(line, linestyle=":")

        # Fill in space between thresholds
        ax.fill_between(x, y2, 0, alpha=0.5, color="red")
        ax.fill_between(x, y1, y2, alpha=0.5, color="yellow")
        ax.fill_between(
            x,
            y1,
            max(
                max(self.greenThresholdFunction(self.pop_count_per_sqkm)),
                self.feature_length_per_pop,
            ),
            alpha=0.5,
            color="green",
        )

        # Plot pont as circle ("o").
        ax.plot(
            self.pop_count_per_sqkm,
            self.feature_length_per_pop,
            "o",
            color="black",
            label="location",
        )

        ax.legend()

        img_data = StringIO()
        plt.savefig(img_data, format="svg")
        self.result.svg = img_data.getvalue()
        logging.debug("Successful SVG figure creation")
        plt.close("all")
        return True

    async def get_zonal_stats_population(self, bpolys: dict) -> Record:
        """Derive zonal population stats for given GeoJSON geometry.

        This is based on the Global Human Settlement Layer Population.
        """
        logging.info("Get population inside polygon")
        query = """
            SELECT
            SUM(
                (public.ST_SummaryStats(
                    public.ST_Clip(
                        rast,
                        st_setsrid(public.ST_GeomFromGeoJSON($1), 4326)
                    )
                )
            ).sum) population
            ,public.ST_Area(
                st_setsrid(public.ST_GeomFromGeoJSON($2)::public.geography, 4326)
            ) / (1000*1000) as area_sqkm
            FROM ghs_pop
            WHERE
             public.ST_Intersects(
                rast,
                st_setsrid(public.ST_GeomFromGeoJSON($3), 4326)
             )
            """
        polygon = json.dumps(bpolys["features"][0]["geometry"])  # Geometry only
        data = (polygon, polygon, polygon)
        async with db_client.get_connection() as conn:
            return await conn.fetchrow(query, *data)
