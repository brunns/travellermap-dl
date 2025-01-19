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
from collections.abc import Sequence
from itertools import product
from pathlib import Path

import httpx
import pydantic
import sqlalchemy
from pythonjsonlogger.json import JsonFormatter
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Session
from tqdm import tqdm
from yarl import URL

STARPORT_DATA = [
    {
        "value": "A",
        "name": "Class A",
        "description": "Excellent quality installation. Refined fuel available. Annual maintenance overhaul available. Shipyard capable of constructing starships and non-starships present. Naval base and/or scout base may be present.",
    },
    {
        "value": "B",
        "name": "Class B",
        "description": "Good quality installation. Refined fuel available. Annual maintenance overhaul available. Shipyard capable of constructing non-starships present. Naval base and/or scout base may be present.",
    },
    {
        "value": "C",
        "name": "Class C",
        "description": "Routine quality installation. Only unrefined fuel available. Reasonable repair facilities present. Scout base may be present.",
    },
    {"value": "D", "name": "Class D", "description": ""},
    {"value": "E", "name": "Class E", "description": ""},
    {"value": "X", "name": "Class X", "description": ""},
]
SIZE_DATA = [
    {"value": "0", "description": ""},
    {"value": "1", "description": ""},
    {"value": "2", "description": ""},
    {"value": "3", "description": ""},
    {"value": "4", "description": ""},
    {"value": "5", "description": ""},
    {"value": "6", "description": ""},
    {"value": "7", "description": ""},
    {"value": "8", "description": ""},
    {"value": "9", "description": ""},
    {"value": "A", "description": ""},
]
ATMOSPHERE_DATA = [
    {"value": "0", "description": ""},
    {"value": "1", "description": ""},
    {"value": "2", "description": ""},
    {"value": "3", "description": ""},
    {"value": "4", "description": ""},
    {"value": "5", "description": ""},
    {"value": "6", "description": ""},
    {"value": "7", "description": ""},
    {"value": "8", "description": ""},
    {"value": "9", "description": ""},
    {"value": "A", "description": ""},
    {"value": "B", "description": ""},
    {"value": "C", "description": ""},
]
HYDROSPHERE_DATA = [
    {"value": "0", "description": ""},
    {"value": "1", "description": ""},
    {"value": "2", "description": ""},
    {"value": "3", "description": ""},
    {"value": "4", "description": ""},
    {"value": "5", "description": ""},
    {"value": "6", "description": ""},
    {"value": "7", "description": ""},
    {"value": "8", "description": ""},
    {"value": "9", "description": ""},
    {"value": "A", "description": ""},
]
GOVERNMENT_DATA = [
    {"value": "0", "description": ""},
    {"value": "1", "description": ""},
    {"value": "2", "description": ""},
    {"value": "3", "description": ""},
    {"value": "4", "description": ""},
    {"value": "5", "description": ""},
    {"value": "6", "description": ""},
    {"value": "7", "description": ""},
    {"value": "8", "description": ""},
    {"value": "9", "description": ""},
    {"value": "A", "description": ""},
    {"value": "B", "description": ""},
    {"value": "C", "description": ""},
    {"value": "D", "description": ""},
]
POPULATION_DATA = [
    {"value": "0", "description": ""},
    {"value": "1", "description": ""},
    {"value": "2", "description": ""},
    {"value": "3", "description": ""},
    {"value": "4", "description": ""},
    {"value": "5", "description": ""},
    {"value": "6", "description": ""},
    {"value": "7", "description": ""},
    {"value": "8", "description": ""},
    {"value": "9", "description": ""},
    {"value": "A", "description": ""},
]
LAW_LEVEL_DATA = [
    {"value": "0", "description": ""},
    {"value": "1", "description": ""},
    {"value": "2", "description": ""},
    {"value": "3", "description": ""},
    {"value": "4", "description": ""},
    {"value": "5", "description": ""},
    {"value": "6", "description": ""},
    {"value": "7", "description": ""},
    {"value": "8", "description": ""},
    {"value": "9", "description": ""},
    {"value": "A", "description": ""},
]
TECH_LEVEL_DATA = [
    {"value": "0", "name": "", "description": ""},
    {"value": "1", "name": "", "description": ""},
    {"value": "2", "name": "", "description": ""},
    {"value": "3", "name": "", "description": ""},
    {"value": "4", "name": "", "description": ""},
    {"value": "5", "name": "", "description": ""},
    {"value": "6", "name": "", "description": ""},
    {"value": "7", "name": "", "description": ""},
    {"value": "8", "name": "", "description": ""},
    {"value": "9", "name": "", "description": ""},
    {"value": "A", "name": "", "description": ""},
    {"value": "B", "name": "", "description": ""},
    {"value": "C", "name": "", "description": ""},
    {"value": "D", "name": "", "description": ""},
    {"value": "E", "name": "", "description": ""},
    {"value": "F", "name": "", "description": ""},
    {"value": "G", "name": "", "description": ""},
]

VERSION = "0.1.0"

LOG_LEVELS = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
logger = logging.getLogger(__name__)


def main() -> None:
    args = parse_args()

    args.output_location.mkdir(parents=True, exist_ok=True)
    if args.populate_database:
        args.database_location.unlink(missing_ok=True)
        engine: sqlalchemy.Engine = sqlalchemy.create_engine(f"sqlite+pysqlite:///{args.database_location}")
        init_database(engine)
    else:
        engine = None

    with (
        httpx.Client(timeout=30, transport=httpx.HTTPTransport(retries=5)) as client,
        Session(engine) if engine else None as session,
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

            if args.populate_database:
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

    return ApiSector.model_validate(dict(response.json(), Milieu=sector.milieu))


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


class ApiName(pydantic.BaseModel):
    text: str = pydantic.Field(..., alias="Text")
    lang: str | None = pydantic.Field(None, alias="Lang")
    source: str | None = pydantic.Field(None, alias="Source")


class ApiProduct(pydantic.BaseModel):
    author: str = pydantic.Field(..., alias="Author")
    title: str = pydantic.Field(..., alias="Title")
    publisher: str = pydantic.Field(..., alias="Publisher")
    ref: str = pydantic.Field(..., alias="Ref")


class ApiDataFile(pydantic.BaseModel):
    source: str = pydantic.Field(..., alias="Source")
    milieu: str = pydantic.Field(..., alias="Milieu")


class ApiSubsector(pydantic.BaseModel):
    name: str = pydantic.Field(..., alias="Name")
    index: str = pydantic.Field(..., alias="Index")
    index_number: int = pydantic.Field(..., alias="IndexNumber")


class ApiAllegiance(pydantic.BaseModel):
    name: str = pydantic.Field(..., alias="Name")
    code: str = pydantic.Field(..., alias="Code")
    base: str | None = pydantic.Field(None, alias="Base")


class ApiBorder(pydantic.BaseModel):
    wrap_label: bool | None = pydantic.Field(None, alias="WrapLabel")
    allegiance: str = pydantic.Field(..., alias="Allegiance")
    label_position: str = pydantic.Field(..., alias="LabelPosition")
    path: str = pydantic.Field(..., alias="Path")
    label: str | None = pydantic.Field(None, alias="Label")
    show_label: bool | None = pydantic.Field(None, alias="ShowLabel")


class ApiRoute(pydantic.BaseModel):
    start: str = pydantic.Field(..., alias="Start")
    end: str = pydantic.Field(..., alias="End")
    end_offset_x: int | None = pydantic.Field(None, alias="EndOffsetX")
    allegiance: str | None = pydantic.Field(None, alias="Allegiance")
    end_offset_y: int | None = pydantic.Field(None, alias="EndOffsetY")
    start_offset_x: int | None = pydantic.Field(None, alias="StartOffsetX")


class ApiSector(pydantic.BaseModel):
    x: int = pydantic.Field(..., alias="X")
    y: int = pydantic.Field(..., alias="Y")
    milieu: str | None = pydantic.Field(None, alias="Milieu")
    abbreviation: str | None = pydantic.Field(None, alias="Abbreviation")
    tags: str = pydantic.Field(..., alias="Tags")
    names: list[ApiName] = pydantic.Field(..., alias="Names")

    credits: list | None = pydantic.Field(None, alias="Credits")
    products: list[ApiProduct] | None = pydantic.Field(None, alias="Products")
    data_file: ApiDataFile | None = pydantic.Field(None, alias="DataFile")
    subsectors: list[ApiSubsector] | None = pydantic.Field(None, alias="Subsectors")
    allegiances: list[ApiAllegiance] | None = pydantic.Field(None, alias="Allegiances")
    stylesheet: str | None = pydantic.Field(None, alias="Stylesheet")
    labels: list | None = pydantic.Field(None, alias="Labels")
    borders: list[ApiBorder] | None = pydantic.Field(None, alias="Borders")
    regions: list | None = pydantic.Field(None, alias="Regions")
    routes: list[ApiRoute] | None = pydantic.Field(None, alias="Routes")


class ApiModel(pydantic.BaseModel):
    sectors: list[ApiSector] = pydantic.Field(..., alias="Sectors")


class Base(sqlalchemy.orm.DeclarativeBase):
    pass


class Milieu(Base):
    __tablename__ = "milieus"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(
        sqlalchemy.String, nullable=False, unique=True
    )  # Milieu identifier (e.g., "M1105", "M1120")
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # Additional information about the milieu

    # Relationships to other tables
    sector_data = sqlalchemy.orm.relationship("Sector", back_populates="milieu")

    def __repr__(self) -> str:
        return f"<Milieu(name='{self.name}', description='{self.description}')>"


class Sector(Base):
    __tablename__ = "sectors"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    x_coordinate = sqlalchemy.Column(sqlalchemy.Float, nullable=False)  # X-coordinate in galaxy
    y_coordinate = sqlalchemy.Column(sqlalchemy.Float, nullable=False)  # Y-coordinate in galaxy
    milieu_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("milieus.id"), nullable=False
    )  # Milieu foreign key

    UniqueConstraint("name", "milieu_id")

    # Relationship to subsectors
    subsectors = sqlalchemy.orm.relationship("Subsector", back_populates="sector", cascade="all, delete-orphan")

    # Relationship to milieu
    milieu = sqlalchemy.orm.relationship("Milieu", back_populates="sector_data")

    def __repr__(self) -> str:
        return (
            f"<Sector(name='{self.name}', x={self.x_coordinate}, y={self.y_coordinate}, milieu='{self.milieu.name}')>"
        )


class Subsector(Base):
    __tablename__ = "subsectors"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    index = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    sector_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("sectors.id"), nullable=False)

    UniqueConstraint("name", "sector_id")

    # Relationship to sector
    sector = sqlalchemy.orm.relationship("Sector", back_populates="subsectors")

    # Relationship to worlds
    worlds = sqlalchemy.orm.relationship("World", back_populates="subsector", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Subsector(name='{self.name}', sector='{self.sector.name}', x={self.x_coordinate}, y={self.y_coordinate}, milieu='{self.milieu.name}')>"


class World(Base):
    __tablename__ = "worlds"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    subsector_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("subsectors.id"), nullable=False)
    hex_location = sqlalchemy.Column(
        sqlalchemy.String, nullable=False
    )  # Hex location within the subsector (e.g., "0203")
    population_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("populations.id"), nullable=True
    )  # Population (can be null if unknown)
    tech_level_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("tech_levels.id"), nullable=True
    )  # TechLevel foreign key
    starport_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("starports.id"), nullable=True
    )  # Starport foreign key
    size_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("sizes.id"), nullable=True
    )  # World size foreign key
    atmosphere_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("atmospheres.id"), nullable=True
    )  # Atmosphere foreign key
    hydrosphere_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("hydrospheres.id"), nullable=True
    )  # Hydrosphere foreign key
    government_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("governments.id"), nullable=True
    )  # Government type foreign key
    law_level_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("law_levels.id"), nullable=True
    )  # Law level foreign key
    trade_codes = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # Trade codes as a comma-separated string
    zone = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    bases = sqlalchemy.Column(sqlalchemy.String, nullable=False)

    UniqueConstraint("hex_location", "subsector_id")

    # Relationship to subsector
    subsector = sqlalchemy.orm.relationship("Subsector", back_populates="worlds")

    # Relationships to reference tables
    starport = sqlalchemy.orm.relationship("Starport")
    size = sqlalchemy.orm.relationship("Size")
    atmosphere = sqlalchemy.orm.relationship("Atmosphere")
    hydrosphere = sqlalchemy.orm.relationship("Hydrosphere")
    population = sqlalchemy.orm.relationship("Population")
    government = sqlalchemy.orm.relationship("Government")
    law_level = sqlalchemy.orm.relationship("LawLevel")
    tech_level = sqlalchemy.orm.relationship("TechLevel")

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
        )


class Starport(Base):
    """Starport types - see https://wiki.travellerrpg.com/Starport"""

    __tablename__ = "starports"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<Starport(value='{self.value}', name='{self.name}', description='{self.description}')>"


class Size(Base):
    __tablename__ = "sizes"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<Size(value='{self.value}', description='{self.description}')>"


class Atmosphere(Base):
    __tablename__ = "atmospheres"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<Atmosphere(value='{self.value}', description='{self.description}')>"


class Hydrosphere(Base):
    __tablename__ = "hydrospheres"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<Hydrosphere(value='{self.value}', description='{self.description}')>"


class Government(Base):
    __tablename__ = "governments"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<Government(value='{self.value}', description='{self.description}')>"


class LawLevel(Base):
    __tablename__ = "law_levels"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<LawLevel(value='{self.value}', description='{self.description}')>"


class Population(Base):
    __tablename__ = "populations"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<Population(value='{self.value}', description='{self.description}')>"


class TechLevel(Base):
    __tablename__ = "tech_levels"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<TechLevel(value='{self.value}', name='{self.name}', description='{self.description}')>"


def init_database(engine: sqlalchemy.Engine) -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.execute(sqlalchemy.insert(Starport), STARPORT_DATA)
        session.execute(sqlalchemy.insert(Size), SIZE_DATA)
        session.execute(sqlalchemy.insert(Atmosphere), ATMOSPHERE_DATA)
        session.execute(sqlalchemy.insert(Hydrosphere), HYDROSPHERE_DATA)
        session.execute(sqlalchemy.insert(Government), GOVERNMENT_DATA)
        session.execute(sqlalchemy.insert(Population), POPULATION_DATA)
        session.execute(sqlalchemy.insert(LawLevel), LAW_LEVEL_DATA)
        session.execute(sqlalchemy.insert(TechLevel), TECH_LEVEL_DATA)

        session.commit()


def populate_database(sector: ApiSector, sector_dir: Path, session: Session):
    db_milieu = session.query(Milieu).filter_by(name=sector.milieu).first()
    if not db_milieu:
        db_milieu = Milieu(name=sector.milieu)
        session.add(db_milieu)

    db_sector = Sector(name=sector.names[0].text, milieu=db_milieu, x_coordinate=sector.x, y_coordinate=sector.y)
    session.add(db_sector)

    db_subsectors: dict[str, Subsector] = {}
    for subsector in sector.subsectors:
        db_subsector = Subsector(sector=db_sector, name=subsector.name, index=subsector.index)
        db_subsectors[subsector.index] = db_subsector
    session.add_all(db_subsectors.values())

    with (sector_dir / f"{sector.names[0].text}.tsv").open("r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # {'(Ex)': '(E69-3)', 'Allegiance': 'ImDc', 'Nobility': 'B', 'PBG': '123', 'RU': '-2268', 'Remarks': 'Fl', 'SS': 'A', 'Stars': 'M2 V', 'UWP': 'C9C4733-9', 'W': '8', '[Cx]': '[4726]', '{Ix}': '{ 0 }'}

            starport, size, atmosphere, hydrosphere, population, government, law_level, _, tech_level, *_ = list(
                row["UWP"]
            )

            world = World(
                name=row["Name"],
                subsector=db_subsectors[row["SS"]],
                hex_location=row["Hex"],
                starport=session.query(Starport).filter_by(value=starport).first(),
                size=session.query(Size).filter_by(value=size).first(),
                atmosphere=session.query(Atmosphere).filter_by(value=atmosphere).first(),
                hydrosphere=session.query(Hydrosphere).filter_by(value=hydrosphere).first(),
                population=session.query(Population).filter_by(value=population).first(),
                government=session.query(Government).filter_by(value=government).first(),
                law_level=session.query(LawLevel).filter_by(value=law_level).first(),
                tech_level=session.query(TechLevel).filter_by(value=tech_level).first(),
                zone=row["Zone"],
                bases=row["Bases"],
            )
            session.add(world)

    session.commit()


def parse_args() -> argparse.Namespace:
    args = create_parser().parse_args()
    init_logging(args.verbosity, silence_packages=["urllib3", "httpcore"])

    return args


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
    parser.add_argument("-V", "--version", action="version", version=VERSION)
    return parser


def init_logging(
    verbosity: int,
    handler=None,
    silence_packages: Sequence[str] = (),
):
    handler = handler or logging.StreamHandler(stream=sys.stdout)
    level = LOG_LEVELS[min(verbosity, len(LOG_LEVELS) - 1)]
    msg_format = "%(message)s"
    if level <= logging.DEBUG:
        warnings.filterwarnings("ignore")
        msg_format = "%(asctime)s %(levelname)-8s %(name)s %(module)s.py:%(funcName)s():%(lineno)d %(message)s"
    handler.setFormatter(JsonFormatter(msg_format))
    logging.basicConfig(level=level, format=msg_format, handlers=[handler])

    for package in silence_packages:
        logging.getLogger(package).setLevel(max([level, logging.WARNING]))


if __name__ == "__main__":
    main()
