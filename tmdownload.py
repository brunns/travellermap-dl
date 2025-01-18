#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "SQLAlchemy",
#     "httpx",
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
from io import StringIO
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
            download_json(client, sector, sector_dir, args.travellermap_url)
            if download_tsv(client, sector, sector_dir, args.travellermap_url) and args.download_posters:
                for style, scale in product(["poster", "atlas", "fasa"], [64, 128]):
                    dl_poster(client, sector, sector_dir, args.travellermap_url, style, scale)

            if args.populate_database:
                populate_database(sector, args.travellermap_url, session)


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


def download_json(client: httpx.Client, sector: ApiSector, sector_dir: Path, travellermap_url: URL) -> None:
    sec_text_url = (
        travellermap_url / sector.names[0].text / "metadata" % {"milieu": sector.milieu, "accept": "application/json"}
    )
    response = client.get(str(sec_text_url))
    response.raise_for_status()
    with (sector_dir / f"{sector.names[0].text}.json").open("w") as f:
        f.write(response.text)


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


class ApiSector(pydantic.BaseModel):
    x: int = pydantic.Field(..., alias="X")
    y: int = pydantic.Field(..., alias="Y")
    milieu: str = pydantic.Field(..., alias="Milieu")
    abbreviation: str | None = pydantic.Field(None, alias="Abbreviation")
    tags: str = pydantic.Field(..., alias="Tags")
    names: list[ApiName] = pydantic.Field(..., alias="Names")


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
    subsector_data = sqlalchemy.orm.relationship("Subsector", back_populates="milieu")
    world_data = sqlalchemy.orm.relationship("World", back_populates="milieu")

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
    sector_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("sectors.id"), nullable=False)
    x_coordinate = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)  # Subsector grid X in sector
    y_coordinate = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)  # Subsector grid Y in sector
    milieu_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("milieus.id"), nullable=False
    )  # Milieu foreign key

    # Relationship to sector
    sector = sqlalchemy.orm.relationship("Sector", back_populates="subsectors")

    # Relationship to worlds
    worlds = sqlalchemy.orm.relationship("World", back_populates="subsector", cascade="all, delete-orphan")

    # Relationship to milieu
    milieu = sqlalchemy.orm.relationship("Milieu", back_populates="subsector_data")

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
    population = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)  # Population (can be null if unknown)
    tech_level = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)  # Technology level (optional)
    trade_codes = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # Trade codes as a comma-separated string
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
    milieu_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey("milieus.id"), nullable=False
    )  # Milieu foreign key

    # Relationship to subsector
    subsector = sqlalchemy.orm.relationship("Subsector", back_populates="worlds")

    # Relationship to milieu
    milieu = sqlalchemy.orm.relationship("Milieu", back_populates="world_data")

    # Relationships to reference tables
    starport = sqlalchemy.orm.relationship("Starport")
    size = sqlalchemy.orm.relationship("Size")
    atmosphere = sqlalchemy.orm.relationship("Atmosphere")
    hydrosphere = sqlalchemy.orm.relationship("Hydrosphere")
    government = sqlalchemy.orm.relationship("Government")
    law_level = sqlalchemy.orm.relationship("LawLevel")

    def __repr__(self) -> str:
        return (
            f"<World(name='{self.name}', subsector='{self.subsector.name}', hex='{self.hex_location}', "
            f"population={self.population}, tech_level={self.tech_level}, trade_codes='{self.trade_codes}', "
            f"starport='{self.starport.name if self.starport else None}', size='{self.size.name if self.size else None}', "
            f"atmosphere='{self.atmosphere.name if self.atmosphere else None}', "
            f"hydrosphere='{self.hydrosphere.name if self.hydrosphere else None}', "
            f"government='{self.government.name if self.government else None}', "
            f"law_level='{self.law_level.name if self.law_level else None}', milieu='{self.milieu.name}')>"
        )


class Starport(Base):
    __tablename__ = "starports"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<Starport(name='{self.name}', description='{self.description}')>"


class Size(Base):
    __tablename__ = "sizes"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<Size(name='{self.name}', description='{self.description}')>"


class Atmosphere(Base):
    __tablename__ = "atmospheres"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<Atmosphere(name='{self.name}', description='{self.description}')>"


class Hydrosphere(Base):
    __tablename__ = "hydrospheres"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<Hydrosphere(name='{self.name}', description='{self.description}')>"


class Government(Base):
    __tablename__ = "governments"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<Government(name='{self.name}', description='{self.description}')>"


class LawLevel(Base):
    __tablename__ = "law_levels"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def __repr__(self) -> str:
        return f"<LawLevel(name='{self.name}', description='{self.description}')>"


def init_database(engine: sqlalchemy.Engine) -> None:
    Base.metadata.create_all(engine)


def populate_database(sec: ApiSector, travellermap_url: URL, session: Session):
    milieu = session.query(Milieu).filter_by(name=sec.milieu).first()
    if not milieu:
        milieu = Milieu(name=sec.milieu)
        session.add(milieu)

    sector = session.query(Sector).filter_by(name=sec.names[0].text, milieu=milieu).first()
    if not sector:
        sector = Sector(name=sec.names[0].text, milieu=milieu, x_coordinate=sec.x, y_coordinate=sec.y)
        session.add(sector)

    sec_tsv_url = travellermap_url / "sec" % {"sector": sec.names[0].text, "milieu": sec.milieu, "type": "TabDelimited"}
    response = httpx.get(str(sec_tsv_url))
    response.raise_for_status()
    reader = csv.DictReader(StringIO(response.text), delimiter="\t")
    for row in reader:
        pass

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
