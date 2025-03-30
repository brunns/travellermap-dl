#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "SQLAlchemy",
#     "httpx",
#     "brunns-row",
#     "pydantic",
#     "python-json-logger",
#     "tdqm",
#     "yarl",
# ]
# ///

from __future__ import annotations

import argparse
import csv
import logging
import sys
import warnings
from contextlib import nullcontext
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel, Field, ValidationError
from pythonjsonlogger.json import JsonFormatter
from sqlalchemy import Column, Engine, Float, ForeignKey, Integer, String, UniqueConstraint, create_engine, insert
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import DeclarativeBase, Session, relationship
from tqdm import tqdm
from yarl import URL

if TYPE_CHECKING:
    from collections.abc import Sequence

VERSION = "0.1.0"

LOG_LEVELS = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
logger = logging.getLogger(__name__)

STARPORT_DATA = [
    {"value": "?", "name": "Unknown", "description": "Unknown"},
    {
        "value": "A",
        "name": "Class A",
        "description": "Excellent quality installation. Refined fuel available. Annual maintenance overhaul available. "
        "Shipyard capable of constructing starships and non-starships present. Naval base and/or scout base may be "
        "present.",
    },
    {
        "value": "B",
        "name": "Class B",
        "description": "Good quality installation. Refined fuel available. Annual maintenance overhaul available. "
        "Shipyard capable of constructing non-starships present. Naval base and/or scout base may be present.",
    },
    {
        "value": "C",
        "name": "Class C",
        "description": "Routine quality installation. Only unrefined fuel available. Reasonable repair facilities "
        "present. Scout base may be present.",
    },
    {
        "value": "D",
        "name": "Class D",
        "description": "Poor quality installation. Only unrefined fuel available. No repair or shipyard facilities "
        "present. Scout base may be present.",
    },
    {
        "value": "E",
        "name": "Class E",
        "description": "Frontier Installation. Essentially a marked spot of bedrock with no fuel, facilities, or bases "
        "present.",
    },
    {"value": "X", "name": "Class X", "description": "No starport. No provision is made for any ship landings."},
    {
        "value": "F",
        "name": "Spaceport Class F",
        "description": "Good Quality. Minor damage repairable. Unrefined fuel available.",
    },
    {
        "value": "G",
        "name": "Spaceport Class G",
        "description": "Poor Quality. Superficial repairs possible. Unrefined fuel available.",
    },
    {"value": "H", "name": "Spaceport Class H", "description": "Primitive Quality. No repairs or fuel available."},
    {"value": "Y", "name": "None", "description": "None."},
]

SIZE_DATA = [
    {"value": "?", "description": "Unknown"},
    {"value": "0", "description": "Asteroid/Planetoid Belt."},
    {"value": "1", "description": "1000 miles (1600 km) ."},
    {"value": "2", "description": "2000 miles (3200 km)."},
    {"value": "3", "description": "3000 miles (4800 km)."},
    {"value": "4", "description": "4000 miles (6400 km)."},
    {"value": "5", "description": "5000 miles (8000 km)."},
    {"value": "6", "description": "6000 miles (9600 km)."},
    {"value": "7", "description": "7000 miles (11200 km)."},
    {"value": "8", "description": "8000 miles (12800 km) ."},
    {"value": "9", "description": "9000 miles (14400 km)."},
    {"value": "A", "description": "10000 miles (16000 km)."},
    {"value": "B", "description": "11000 miles (18800 km)."},
    {"value": "C", "description": "12000 miles (19200 km)."},
    {"value": "D", "description": "13000 miles (20800 km)."},
    {"value": "E", "description": "14000 miles (22400 km)."},
    {"value": "F", "description": "15000 miles (24000 km)."},
]

ATMOSPHERE_DATA = [
    {"value": "?", "description": "Unknown"},
    {"value": "0", "description": "No atmosphere."},
    {"value": "1", "description": "Trace."},
    {"value": "2", "description": "Very thin, tainted."},
    {"value": "3", "description": "Very thin."},
    {"value": "4", "description": "Thin, tainted."},
    {"value": "5", "description": "Thin."},
    {"value": "6", "description": "Standard."},
    {"value": "7", "description": "Standard, tainted."},
    {"value": "8", "description": "Dense."},
    {"value": "9", "description": "Dense, tainted."},
    {"value": "A", "description": "Exotic."},
    {"value": "B", "description": "Corrosive."},
    {"value": "C", "description": "Insidious."},
    {"value": "D", "description": "Dense, high."},
    {"value": "E", "description": "Ellipsoid."},
    {"value": "F", "description": "Thin, low."},
]

HYDROSPHERE_DATA = [
    {"value": "?", "description": "Unknown"},
    {"value": "0", "description": "No water."},
    {"value": "1", "description": "10% or less water."},
    {"value": "2", "description": "11-20% water."},
    {"value": "3", "description": "21-30% water."},
    {"value": "4", "description": "31-40% water."},
    {"value": "5", "description": "41-50% water."},
    {"value": "6", "description": "51-60% water."},
    {"value": "7", "description": "61-70% water."},
    {"value": "8", "description": "71-80% water."},
    {"value": "9", "description": "81-90% water."},
    {"value": "A", "description": "91-100% water."},
]

GOVERNMENT_DATA = [
    {"value": "?", "description": "Unknown."},
    {"value": "0", "description": "No Government Structure."},
    {"value": "1", "description": "Company/Corporation."},
    {"value": "2", "description": "Participating Democracy."},
    {"value": "3", "description": "Self-Perpetuating Oligarchy."},
    {"value": "4", "description": "Representative Democracy."},
    {"value": "5", "description": "Feudal Technocracy."},
    {"value": "6", "description": "Captive Government / Colony."},
    {"value": "7", "description": "Balkanization."},
    {"value": "8", "description": "Civil Service Bureaucracy."},
    {"value": "9", "description": "Impersonal Bureaucracy."},
    {"value": "A", "description": "Charismatic Dictator."},
    {"value": "B", "description": "Non-Charismatic Dictator."},
    {"value": "C", "description": "Charismatic Oligarchy."},
    {"value": "D", "description": "Religious Dictatorship."},
    {"value": "E", "description": "Religious Autocracy."},
    {"value": "F", "description": "Totalitarian Oligarchy."},
    {"value": "G", "description": "Small Station or Facility (Aslan)."},
    {"value": "H", "description": "Split Clan Control (Aslan)."},
    {"value": "J", "description": "Single On-world Clan Control (Aslan)."},
    {"value": "K", "description": "Single Multi-world Clan Control (Aslan)."},
    {"value": "L", "description": "Major Clan Control (Aslan)."},
    {"value": "M", "description": "Vassal Clan Control (Aslan) or Military Dictatorship / Junta."},
    {"value": "N", "description": "Major Vassal Clan Control (Aslan)."},
    {"value": "P", "description": "Small Station or Facility (K'kree)."},
    {"value": "Q", "description": "Krurruna or Krumanak Rule for Off-world Steppelord (K'kree) or Interim Government."},
    {"value": "R", "description": "Steppelord On-world Rule (K'kree)."},
    {"value": "S", "description": "Sept (Hiver) or Slave World."},
    {"value": "T", "description": "Unsupervised Anarchy (Hiver) or Technologically Elevated Dictator."},
    {"value": "U", "description": "Supervised Anarchy (Hiver)."},
    {"value": "V", "description": "Viral Hell."},
    {"value": "W", "description": "Committee (Hiver)."},
    {"value": "X", "description": "Droyne Hierarchy (Droyne)."},
    {"value": "Y", "description": "Unassigned / Undefined."},
    {"value": "Z", "description": "Unassigned / Undefined."},
]

POPULATION_DATA = [
    {"value": "?", "description": "Unknown"},
    {"value": "0", "description": "Low population (up to a few dozen)."},
    {"value": "1", "description": "Tens to hundreds."},
    {"value": "2", "description": "Hundreds to thousands."},
    {"value": "3", "description": "Thousands to tens of thousands."},
    {"value": "4", "description": "Tens of thousands to hundreds of thousands."},
    {"value": "5", "description": "Hundreds of thousands to millions."},
    {"value": "6", "description": "Millions to tens of millions."},
    {"value": "7", "description": "Tens of millions to hundreds of millions."},
    {"value": "8", "description": "Hundreds of millions to billions."},
    {"value": "9", "description": "Billions."},
    {"value": "A", "description": "Tens of billions."},
    {"value": "B", "description": "Hundreds of billions."},
    {"value": "C", "description": "Trillions."},
]

LAW_LEVEL_DATA = [
    {"value": "?", "description": "Unknown"},
    {"value": "0", "description": "No law."},
    {"value": "1", "description": "Low law, unrestricted weapons."},
    {"value": "2", "description": "Some firearm restrictions."},
    {"value": "3", "description": "Heavy weapon restrictions."},
    {"value": "4", "description": "Personal concealable weapons banned."},
    {"value": "5", "description": "No firearms outside home."},
    {"value": "6", "description": "All firearms banned."},
    {"value": "7", "description": "All weapons banned."},
    {"value": "8", "description": "Civilian movement controlled."},
    {"value": "9", "description": "Extreme social control."},
    {"value": "A", "description": "Full control of daily life."},
    {"value": "B", "description": ""},
    {"value": "C", "description": ""},
    {"value": "D", "description": ""},
    {"value": "E", "description": ""},
    {"value": "F", "description": ""},
    {"value": "G", "description": ""},
    {"value": "H", "description": ""},
    {"value": "I", "description": ""},
    {"value": "J", "description": ""},
]

TECH_LEVEL_DATA = [
    {"value": "?", "name": "Unknown", "description": "Unknown technology level."},
    {"value": "0", "name": "Stone Age", "description": "Pre-industrial, no technology."},
    {"value": "1", "name": "Bronze/Iron Age", "description": "Basic metallurgy, sailing ships."},
    {"value": "2", "name": "Renaissance", "description": "Gunpowder, printing, early scientific development."},
    {"value": "3", "name": "Industrial Revolution", "description": "Steam power, railroads, simple factories."},
    {"value": "4", "name": "Late Industrial Age", "description": "Combustion engines, radio, aircraft."},
    {"value": "5", "name": "Early Space Age", "description": "Basic computers, early rockets, satellites."},
    {"value": "6", "name": "Fusion Age", "description": "Nuclear power, early fusion, advanced electronics."},
    {"value": "7", "name": "Interplanetary Age", "description": "Basic space travel, colonization of planets."},
    {"value": "8", "name": "Jump Drive Age", "description": "Basic interstellar travel, jump-1 starships."},
    {"value": "9", "name": "Expanded Star Travel", "description": "Jump-2 technology, advanced shipbuilding."},
    {"value": "A", "name": "Interstellar Society", "description": "Jump-3 technology, high automation."},
    {
        "value": "B",
        "name": "Lower Average Imperial.",
        "description": "Jump-4 technology, significant AI and cybernetics.",
    },
    {"value": "C", "name": "Average Imperial", "description": "Jump-5 technology, planetary-scale engineering."},
    {
        "value": "D",
        "name": "Above Average Imperial",
        "description": "Jump-6 technology, advanced artificial intelligence.",
    },
    {
        "value": "E",
        "name": "Above Average Imperial",
        "description": "Highly efficient starships, major genetic engineering.",
    },
    {
        "value": "F",
        "name": "Technical Imperial Maximum",
        "description": "Extremely high technology, nearly self-sufficient systems.",
    },
    {
        "value": "G",
        "name": "Robots",
        "description": "Near-complete automation, and highly efficient energy generation.",
    },
    {
        "value": "H",
        "name": "Artificial Intelligence",
        "description": "Extensive megastructures, and advanced matter manipulation.",
    },
    {"value": "I", "name": "Personal Disintegrators", "description": ""},
    {"value": "J", "name": "", "description": ""},
    {"value": "K", "name": "Plastic Metals", "description": ""},
    {"value": "L", "name": "Magic", "description": "Comprehensible only as technological magic."},
]


def main() -> None:
    args = create_parser().parse_args()

    init_logging(args.verbosity, log_json=args.log_json, silence_packages=["urllib3", "httpcore", "httpx"])
    logger.info("args: %s", args, extra=vars(args))

    args.output_location.mkdir(parents=True, exist_ok=True)
    if args.populate_database:
        args.database_location.unlink(missing_ok=True)
        engine: Engine | None = create_engine(f"sqlite+pysqlite:///{args.database_location}")
        init_database(engine)
    else:
        engine = None

    with (
        httpx.Client(timeout=30, transport=httpx.HTTPTransport(retries=5)) as client,
        Session(engine) if engine else nullcontext() as session,
    ):
        sectors = get_sectors(client, args.output_location, args.travellermap_url)

        pbar = tqdm(sorted(sectors, key=lambda s: (abs(s.x) + abs(s.y), s.names[0].text)))
        for sector in pbar:
            pbar.set_description(f"sector {sector.names[0].text}, milieu {sector.milieu}, at {sector.x},{sector.y}")
            sector_dir = args.output_location / sector.names[0].text / sector.milieu
            sector_dir.mkdir(parents=True, exist_ok=True)

            download_text(client, sector, sector_dir, args.travellermap_url)
            decorated_sector = download_json(client, sector, sector_dir, args.travellermap_url)
            if download_tsv(client, sector, sector_dir, args.travellermap_url) and args.download_posters:
                for style, scale in product(["poster", "atlas", "fasa"], [64, 128]):
                    dl_poster(client, sector, sector_dir, args.travellermap_url, style, scale)

            if args.populate_database and session:
                populate_database(decorated_sector, sector_dir, session)


def get_sectors(client: httpx.Client, output_location: Path, travellermap_url: URL) -> Sequence[ApiSector]:
    response = client.get(str(travellermap_url % {"tag": "OTU", "requireData": 1}))
    response.raise_for_status()
    with (output_location / "sectors.json").open("w") as f:
        f.write(response.text)
    data = ApiModel.model_validate(response.json())
    return data.sectors


def download_text(client: httpx.Client, sector: ApiSector, sector_dir: Path, travellermap_url: URL) -> None:
    sec_text_url = travellermap_url / "sec" % {"sector": sector.names[0].text, "milieu": sector.milieu}
    response = client.get(str(sec_text_url))
    response.raise_for_status()
    with (sector_dir / f"{sector.names[0].text}.txt").open("w") as f:
        f.write(response.text)


def download_json(client: httpx.Client, sector: ApiSector, sector_dir: Path, travellermap_url: URL) -> ApiSector:
    sec_text_url = (
        travellermap_url / sector.names[0].text / "metadata" % {"milieu": sector.milieu, "accept": "application/json"}
    )
    response = client.get(str(sec_text_url))
    response.raise_for_status()
    with (sector_dir / f"{sector.names[0].text}.json").open("w") as f:
        f.write(response.text)

    response_json = response.json()
    try:
        return ApiSector.model_validate(dict(response_json, Milieu=sector.milieu))
    except ValidationError as e:
        logger.exception("ValidationError", extra=dict(response_json), exc_info=e)
        raise


def download_tsv(client: httpx.Client, sector: ApiSector, sector_dir: Path, travellermap_url: URL) -> bool:
    sec_tsv_url = (
        travellermap_url / "sec" % {"sector": sector.names[0].text, "milieu": sector.milieu, "type": "TabDelimited"}
    )
    response = client.get(str(sec_tsv_url))
    response.raise_for_status()
    if response.text:
        with (sector_dir / f"{sector.names[0].text}.tsv").open("w") as f:
            f.write(response.text)
            return True
    else:
        return False


def dl_poster(
    client: httpx.Client, sector: ApiSector, sector_dir: Path, travellermap_url: URL, style: str, scale: int
) -> None:
    sec_tile_url = (
        travellermap_url
        / sector.names[0].text
        / "image"
        % {"milieu": sector.milieu, "accept": "application/pdf", "style": style, "options": "9211", "scale": scale}
    )
    pdf_path = sector_dir / f"{sector.names[0].text} {style} {scale}.pdf"
    if not pdf_path.exists():
        response = client.get(str(sec_tile_url))
        response.raise_for_status()
        with pdf_path.open("wb") as f:
            f.write(response.content)


class ApiName(BaseModel):
    text: str = Field(..., alias="Text")
    lang: str | None = Field(None, alias="Lang")
    source: str | None = Field(None, alias="Source")


class ApiProduct(BaseModel):
    author: str | None = Field(None, alias="Author")
    title: str | None = Field(None, alias="Title")
    publisher: str | None = Field(None, alias="Publisher")
    ref: str | None = Field(None, alias="Ref")


class ApiDataFile(BaseModel):
    source: str | None = Field(None, alias="Source")
    milieu: str | None = Field(None, alias="Milieu")


class ApiSubsector(BaseModel):
    name: str = Field(..., alias="Name")
    index: str = Field(..., alias="Index")
    index_number: int = Field(..., alias="IndexNumber")


class ApiAllegiance(BaseModel):
    name: str | None = Field(None, alias="Name")
    code: str | None = Field(None, alias="Code")
    base: str | None = Field(None, alias="Base")


class ApiBorder(BaseModel):
    wrap_label: bool | None = Field(None, alias="WrapLabel")
    allegiance: str | None = Field(None, alias="Allegiance")
    label_position: str = Field(..., alias="LabelPosition")
    path: str = Field(..., alias="Path")
    label: str | None = Field(None, alias="Label")
    show_label: bool | None = Field(None, alias="ShowLabel")


class ApiRoute(BaseModel):
    start: str = Field(..., alias="Start")
    end: str = Field(..., alias="End")
    end_offset_x: int | None = Field(None, alias="EndOffsetX")
    allegiance: str | None = Field(None, alias="Allegiance")
    end_offset_y: int | None = Field(None, alias="EndOffsetY")
    start_offset_x: int | None = Field(None, alias="StartOffsetX")


class ApiSector(BaseModel):
    x: int = Field(..., alias="X")
    y: int = Field(..., alias="Y")
    milieu: str | None = Field(None, alias="Milieu")
    abbreviation: str | None = Field(None, alias="Abbreviation")
    tags: str = Field(..., alias="Tags")
    names: list[ApiName] = Field(..., alias="Names")

    credits: list | None = Field(None, alias="Credits")
    products: list[ApiProduct] | None = Field(None, alias="Products")
    data_file: ApiDataFile | None = Field(None, alias="DataFile")
    subsectors: list[ApiSubsector] | None = Field(None, alias="Subsectors")
    allegiances: list[ApiAllegiance] | None = Field(None, alias="Allegiances")
    stylesheet: str | None = Field(None, alias="Stylesheet")
    labels: list | None = Field(None, alias="Labels")
    borders: list[ApiBorder] | None = Field(None, alias="Borders")
    regions: list | None = Field(None, alias="Regions")
    routes: list[ApiRoute] | None = Field(None, alias="Routes")


class ApiModel(BaseModel):
    sectors: list[ApiSector] = Field(..., alias="Sectors")


class Base(DeclarativeBase):
    pass


class Milieu(Base):
    __tablename__ = "milieus"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)  # Milieu identifier (e.g., "M1105", "M1120")
    description = Column(String, nullable=True)  # Additional information about the milieu

    # Relationships to other tables
    sector_data = relationship("Sector", back_populates="milieu")

    def __repr__(self) -> str:
        return f"<Milieu(name='{self.name}', description='{self.description}')>"


class Sector(Base):
    __tablename__ = "sectors"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    x_coordinate = Column(Float, nullable=False)  # X-coordinate in galaxy
    y_coordinate = Column(Float, nullable=False)  # Y-coordinate in galaxy
    milieu_id = Column(Integer, ForeignKey("milieus.id"), nullable=False)  # Milieu foreign key

    UniqueConstraint("name", "milieu_id")

    # Relationship to subsectors
    subsectors = relationship("Subsector", back_populates="sector", cascade="all, delete-orphan")

    # Relationship to milieu
    milieu = relationship("Milieu", back_populates="sector_data")

    def __repr__(self) -> str:
        return (
            f"<Sector(name='{self.name}', x={self.x_coordinate}, y={self.y_coordinate}, milieu='{self.milieu.name}')>"
        )


class Subsector(Base):
    __tablename__ = "subsectors"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    index = Column(String, nullable=False)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False)

    UniqueConstraint("name", "sector_id")

    # Relationship to sector
    sector = relationship("Sector", back_populates="subsectors")

    # Relationship to worlds
    worlds = relationship("World", back_populates="subsector", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<Subsector(name='{self.name}', sector='{self.sector.name}', index={self.index}, "
            f"milieu='{self.sector.milieu.name}')>"
        )


class World(Base):
    __tablename__ = "worlds"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    subsector_id = Column(Integer, ForeignKey("subsectors.id"), nullable=False)
    hex_location = Column(String, nullable=False)  # Hex location within the subsector (e.g., "0203")
    population_id = Column(Integer, ForeignKey("populations.id"), nullable=False)  # Population (can be null if unknown)
    tech_level_id = Column(Integer, ForeignKey("tech_levels.id"), nullable=False)  # TechLevel foreign key
    starport_id = Column(Integer, ForeignKey("starports.id"), nullable=False)  # Starport foreign key
    size_id = Column(Integer, ForeignKey("sizes.id"), nullable=False)  # World size foreign key
    atmosphere_id = Column(Integer, ForeignKey("atmospheres.id"), nullable=False)  # Atmosphere foreign key
    hydrosphere_id = Column(Integer, ForeignKey("hydrospheres.id"), nullable=False)  # Hydrosphere foreign key
    government_id = Column(Integer, ForeignKey("governments.id"), nullable=False)  # Government type foreign key
    law_level_id = Column(Integer, ForeignKey("law_levels.id"), nullable=False)  # Law level foreign key
    trade_codes = Column(String, nullable=True)  # Trade codes as a comma-separated string
    zone = Column(String, nullable=False)
    bases = Column(String, nullable=False)

    UniqueConstraint("hex_location", "subsector_id")

    # Relationship to subsector
    subsector = relationship("Subsector", back_populates="worlds")

    # Relationships to reference tables
    starport = relationship("Starport")
    size = relationship("Size")
    atmosphere = relationship("Atmosphere")
    hydrosphere = relationship("Hydrosphere")
    population = relationship("Population")
    government = relationship("Government")
    law_level = relationship("LawLevel")
    tech_level = relationship("TechLevel")

    @property
    def uwp(self) -> str:
        return (
            f"{self.starport.value}{self.size.value}{self.atmosphere.value}{self.hydrosphere.value}"
            f"{self.population.value}{self.government.value}{self.law_level.value}-{self.tech_level.value}"
        )

    def __repr__(self) -> str:
        return (
            f"<World(name='{self.name}', "
            f"subsector='{self.subsector.name}', "
            f"hex='{self.hex_location}', "
            f"population={self.population.value}, "
            f"starport='{self.starport.name if self.starport else None}', "
            f"size='{self.size.value if self.size else None}', "
            f"atmosphere='{self.atmosphere.value if self.atmosphere else None}', "
            f"hydrosphere='{self.hydrosphere.value if self.hydrosphere else None}', "
            f"government='{self.government.value if self.government else None}', "
            f"law_level='{self.law_level.value if self.law_level else None}', "
            f"tech_level='{self.tech_level.name if self.law_level else None}'"
            f"zone='{self.zone}', "
            f"bases='{self.bases}', "
            ")>"
        )


class Starport(Base):
    """Starport types - see https://wiki.travellerrpg.com/Starport"""

    __tablename__ = "starports"

    id = Column(Integer, primary_key=True)
    value = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Starport(value='{self.value}', name='{self.name}', description='{self.description}')>"


class Size(Base):
    __tablename__ = "sizes"

    id = Column(Integer, primary_key=True)
    value = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Size(value='{self.value}', description='{self.description}')>"


class Atmosphere(Base):
    __tablename__ = "atmospheres"

    id = Column(Integer, primary_key=True)
    value = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Atmosphere(value='{self.value}', description='{self.description}')>"


class Hydrosphere(Base):
    __tablename__ = "hydrospheres"

    id = Column(Integer, primary_key=True)
    value = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Hydrosphere(value='{self.value}', description='{self.description}')>"


class Government(Base):
    __tablename__ = "governments"

    id = Column(Integer, primary_key=True)
    value = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Government(value='{self.value}', description='{self.description}')>"


class LawLevel(Base):
    __tablename__ = "law_levels"

    id = Column(Integer, primary_key=True)
    value = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<LawLevel(value='{self.value}', description='{self.description}')>"


class Population(Base):
    __tablename__ = "populations"

    id = Column(Integer, primary_key=True)
    value = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Population(value='{self.value}', description='{self.description}')>"


class TechLevel(Base):
    __tablename__ = "tech_levels"

    id = Column(Integer, primary_key=True)
    value = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<TechLevel(value='{self.value}', name='{self.name}', description='{self.description}')>"


def init_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.execute(insert(Starport), STARPORT_DATA)
        session.execute(insert(Size), SIZE_DATA)
        session.execute(insert(Atmosphere), ATMOSPHERE_DATA)
        session.execute(insert(Hydrosphere), HYDROSPHERE_DATA)
        session.execute(insert(Government), GOVERNMENT_DATA)
        session.execute(insert(Population), POPULATION_DATA)
        session.execute(insert(LawLevel), LAW_LEVEL_DATA)
        session.execute(insert(TechLevel), TECH_LEVEL_DATA)

        session.commit()


def populate_database(sector: ApiSector, sector_dir: Path, session: Session) -> None:
    db_milieu = session.query(Milieu).filter_by(name=sector.milieu).first()
    if not db_milieu:
        db_milieu = Milieu(name=sector.milieu)
        session.add(db_milieu)

    db_sector = Sector(name=sector.names[0].text, milieu=db_milieu, x_coordinate=sector.x, y_coordinate=sector.y)
    session.add(db_sector)

    db_subsectors: dict[str, Subsector] = {}
    for subsector in sector.subsectors if sector.subsectors else []:
        db_subsector = Subsector(sector=db_sector, name=subsector.name, index=subsector.index)
        db_subsectors[subsector.index] = db_subsector
    session.add_all(db_subsectors.values())
    session.commit()

    with (sector_dir / f"{sector.names[0].text}.tsv").open("r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # See https://travellermap.com/doc/fileformats#t5-tab-delimited-format for columns

            starport, size, atmosphere, hydrosphere, population, government, law_level, _, tech_level, *_ = list(
                row["UWP"]
            )

            try:
                world = World(
                    name=row["Name"],
                    subsector=db_subsectors[row["SS"]],
                    hex_location=row["Hex"],
                    starport=session.query(Starport).filter_by(value=starport).one(),
                    size=session.query(Size).filter_by(value=size).one(),
                    atmosphere=session.query(Atmosphere).filter_by(value=atmosphere).one(),
                    hydrosphere=session.query(Hydrosphere).filter_by(value=hydrosphere).one(),
                    population=session.query(Population).filter_by(value=population).one(),
                    government=session.query(Government).filter_by(value=government).one(),
                    law_level=session.query(LawLevel).filter_by(value=law_level).one(),
                    tech_level=session.query(TechLevel).filter_by(value=tech_level).one(),
                    zone=row["Zone"],
                    bases=row["Bases"],
                )
                session.add(world)
            except (NoResultFound, IntegrityError, KeyError) as e:
                logger.warning(
                    "Exception for world %s %s %s %s - skipped",
                    sector.milieu,
                    sector.names[0].text,
                    row.get("SS"),
                    row.get("Name"),
                    extra=locals(),
                    exc_info=e,
                )
                session.rollback()
            else:
                session.commit()


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Display status of GitHub Actions..")

    parser.add_argument("-p", "--download-posters", action="store_true", help="Download posters as PDF files")
    parser.add_argument("-d", "--populate-database", action="store_true", help="Populate database with world data")
    parser.add_argument(
        "--travellermap-url",
        type=URL,
        default=URL("https://travellermap.com/data"),
        help="travellermap.com URL. Default: %(default)s",
    )
    parser.add_argument(
        "--output-location",
        type=Path,
        default=Path.cwd() / "out",
        help="Output location. Default: %(default)s",
    )
    parser.add_argument(
        "--database-location",
        type=Path,
        default=Path.cwd() / "out" / "travellermap.db",
        help="Database location. Default: %(default)s",
    )

    parser.add_argument(
        "-v",
        "--verbosity",
        action="count",
        default=0,
        help="specify up to four times to increase verbosity, "
        "i.e. -v to see warnings, -vv for information messages, "
        "-vvv for debug messages, or -vvvv for trace messages.",
    )
    parser.add_argument("-j", "--log-json", action="store_true", help="JSON formatted logging.")
    parser.add_argument("-V", "--version", action="version", version=VERSION)
    return parser


def init_logging(
    verbosity: int,
    handler: logging.Handler | None = None,
    silence_packages: Sequence[str] = (),
    *,
    log_json: bool = False,
) -> None:
    """Initialize logger and warnings according to verbosity argument.
    Verbosity levels of 0-3 supported."""
    handler = handler or logging.StreamHandler(stream=sys.stdout)
    level = LOG_LEVELS[min(verbosity, len(LOG_LEVELS) - 1)]

    if level <= logging.DEBUG:
        msg_format = "%(asctime)s %(levelname)-8s %(name)s %(module)s.py:%(funcName)s():%(lineno)d %(message)s"
        warnings.filterwarnings("ignore")
    else:
        msg_format = "%(message)s"

    handler.setFormatter(JsonFormatter(msg_format) if log_json else logging.Formatter(fmt=msg_format))

    logging.basicConfig(level=level, format=msg_format, handlers=[handler])

    for package in silence_packages:
        logging.getLogger(package).setLevel(max([level, logging.WARNING]))


if __name__ == "__main__":
    main()
