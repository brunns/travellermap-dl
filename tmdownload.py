#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "SQLAlchemy~=2.0",
#     "httpx[http2]~=0.28",
#     "brunns-row~=2.0",
#     "pydantic~=2.0",
#     "python-json-logger~=3.0",
#     "tqdm~=4.0",
#     "yarl~=1.0",
# ]
# ///

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import warnings
from contextlib import nullcontext
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from pydantic import ValidationError
from pythonjsonlogger.json import JsonFormatter
from sqlalchemy import Engine, create_engine, insert
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session
from tqdm import tqdm
from yarl import URL

import db_models
from api_models import ApiModel, ApiSector

if TYPE_CHECKING:
    from collections.abc import Sequence

VERSION = "0.1.0"

LOG_LEVELS = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
logger = logging.getLogger(__name__)


def main() -> None:
    args = create_parser().parse_args()

    init_logging(args.verbosity, log_json=args.log_json, silence_packages=["urllib3", "httpcore", "httpx"])
    logger.info("args: %s", args, extra=vars(args))

    args.output_location.mkdir(parents=True, exist_ok=True)
    if args.populate_database:
        args.database_location.unlink(missing_ok=True)
        engine: Engine | None = create_engine(f"sqlite+pysqlite:///{args.database_location}")
        insert_reference_data(engine)
    else:
        engine = None

    with (
        httpx.Client(timeout=30, transport=httpx.HTTPTransport(http2=True, retries=5)) as client,
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


def insert_reference_data(engine: Engine) -> None:
    db_models.Base.metadata.create_all(engine)
    data_dir = Path(__file__).parent / "data"
    with Session(engine) as session:
        session.execute(insert(db_models.Starport), json.loads((data_dir / "starports.json").read_text()))
        session.execute(insert(db_models.Size), json.loads((data_dir / "sizes.json").read_text()))
        session.execute(insert(db_models.Atmosphere), json.loads((data_dir / "atmospheres.json").read_text()))
        session.execute(insert(db_models.Hydrosphere), json.loads((data_dir / "hydrospheres.json").read_text()))
        session.execute(insert(db_models.Government), json.loads((data_dir / "governments.json").read_text()))
        session.execute(insert(db_models.Population), json.loads((data_dir / "populations.json").read_text()))
        session.execute(insert(db_models.LawLevel), json.loads((data_dir / "law_levels.json").read_text()))
        session.execute(insert(db_models.TechLevel), json.loads((data_dir / "tech_levels.json").read_text()))

        session.commit()


def populate_database(sector: ApiSector, sector_dir: Path, session: Session) -> None:
    db_milieu = session.query(db_models.Milieu).filter_by(name=sector.milieu).first()
    if not db_milieu:
        db_milieu = db_models.Milieu(name=sector.milieu)
        session.add(db_milieu)

    db_sector = db_models.Sector(
        name=sector.names[0].text, milieu=db_milieu, x_coordinate=sector.x, y_coordinate=sector.y
    )
    session.add(db_sector)

    db_subsectors: dict[str, db_models.Subsector] = {}
    for subsector in sector.subsectors or []:
        db_subsector = db_models.Subsector(sector=db_sector, name=subsector.name, index=subsector.index)
        db_subsectors[subsector.index] = db_subsector
    session.add_all(db_subsectors.values())
    session.commit()

    with (sector_dir / f"{sector.names[0].text}.tsv").open("r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # See https://travellermap.com/doc/fileformats#t5-tab-delimited-format for columns

            try:
                starport, size, atmosphere, hydrosphere, population, government, law_level, _, tech_level, *_ = list(
                    row["UWP"]
                )
                ss_index = row["SS"]
                if ss_index not in db_subsectors:
                    db_subsector = db_models.Subsector(sector=db_sector, name="?", index=ss_index)
                    session.add(db_subsector)
                    db_subsectors[ss_index] = db_subsector
                world = db_models.World(
                    name=row["Name"],
                    subsector=db_subsectors[ss_index],
                    hex_location=row["Hex"],
                    starport=get_relation(db_models.Starport, starport, session),
                    size=get_relation(db_models.Size, size, session),
                    atmosphere=get_relation(db_models.Atmosphere, atmosphere, session),
                    hydrosphere=get_relation(db_models.Hydrosphere, hydrosphere, session),
                    population=get_relation(db_models.Population, population, session),
                    government=get_relation(db_models.Government, government, session),
                    law_level=get_relation(db_models.LawLevel, law_level, session),
                    tech_level=get_relation(db_models.TechLevel, tech_level, session),
                    zone=row.get("Zone", ""),
                    bases=row.get("Bases", ""),
                )
                session.add(world)
            except (NoResultFound, IntegrityError, KeyError, ValueError) as e:
                logger.warning(
                    "Exception for world %s, %s, %s, %s, %s - skipped",
                    sector.milieu,
                    sector.names[0].text,
                    row.get("SS"),
                    row.get("Name"),
                    row.get("UWP"),
                    extra=locals(),
                    exc_info=e,
                )
                session.rollback()
            else:
                session.commit()


def get_relation[T: db_models.Base](entity: type[T], key: str, session: Session) -> T:
    try:
        return session.query(entity).filter_by(code=key).one()
    except NoResultFound:
        logger.error("Instance of %s with value %r not found", entity, key)  # noqa: TRY400
        raise


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
