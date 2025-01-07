from pathlib import Path
from time import sleep

import httpx
import pydantic
from tqdm import tqdm
from yarl import URL

BASE_URL = URL("https://travellermap.com/data")
OUT_PATH = Path.cwd() / "out"


class Name(pydantic.BaseModel):
    text: str = pydantic.Field(..., alias="Text")
    lang: str | None = pydantic.Field(None, alias="Lang")
    source: str | None = pydantic.Field(None, alias="Source")


class Sector(pydantic.BaseModel):
    x: int = pydantic.Field(..., alias="X")
    y: int = pydantic.Field(..., alias="Y")
    milieu: str = pydantic.Field(..., alias="Milieu")
    abbreviation: str | None = pydantic.Field(None, alias="Abbreviation")
    tags: str = pydantic.Field(..., alias="Tags")
    names: list[Name] = pydantic.Field(..., alias="Names")

    abbreviation: str | None = pydantic.Field(None, alias="Abbreviation")
    tags: str = pydantic.Field(..., alias="Tags")
    names: list[Name] = pydantic.Field(..., alias="Names")


class Model(pydantic.BaseModel):
    sectors: list[Sector] = pydantic.Field(..., alias="Sectors")


def main():
    OUT_PATH.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=30, transport=httpx.HTTPTransport(retries=5)) as client:
        sectors = get_sectors(client)

        pbar = tqdm(sorted(sectors, key=lambda s: (abs(s.x) + abs(s.y), s.names[0].text)))
        for sector in pbar:
            pbar.set_description(f"sector {sector.names[0].text}, milieu {sector.milieu}, at {sector.x},{sector.y}")
            sector_dir = OUT_PATH / sector.names[0].text / sector.milieu
            sector_dir.mkdir(parents=True, exist_ok=True)

            dl_text(client, sector, sector_dir)
            if dl_tsv(client, sector, sector_dir):
                for style in ["poster", "atlas", "fasa"]:
                    dl_poster(client, sector, sector_dir, style)

        # sec_tsv_url = BASE_URL / "sec" % {"sector": sector.names[0].text, "type": "TabDelimited"}
        # response = httpx.get(str(sec_tsv_url))
        # response.raise_for_status()
        # reader = csv.DictReader(StringIO(response.text), delimiter="\t")
        # for row in reader:
        #     print(row)


def dl_text(client, sector, sector_dir):
    sec_text_url = BASE_URL / "sec" % {"sector": sector.names[0].text, "milieu": sector.milieu}
    response = client.get(str(sec_text_url))
    response.raise_for_status()
    with (sector_dir / f"{sector.names[0].text}.txt").open("w") as f:
        f.write(response.text)


def dl_tsv(client, sector, sector_dir):
    sec_tsv_url = BASE_URL / "sec" % {"sector": sector.names[0].text, "milieu": sector.milieu, "type": "TabDelimited"}
    response = client.get(str(sec_tsv_url))
    response.raise_for_status()
    if response.text:
        with (sector_dir / f"{sector.names[0].text}.tsv").open("w") as f:
            f.write(response.text)
            return True
    else:
        return False


def dl_poster(client, sector, sector_dir, style):
    sec_tile_url = (
        BASE_URL
        / sector.names[0].text
        / "image"
        % {"milieu": sector.milieu, "accept": "application/pdf", "style": style, "options": "9211"}
    )
    pdf_path = sector_dir / f"{sector.names[0].text} {style}.pdf"
    if not pdf_path.exists():
        response = client.get(str(sec_tile_url))
        response.raise_for_status()
        with pdf_path.open("wb") as f:
            f.write(response.content)
        sleep(5)


def get_sectors(client) -> list[Sector]:
    response = client.get(str(BASE_URL))
    response.raise_for_status()
    with (OUT_PATH / "sectors.json").open("w") as f:
        f.write(response.text)
    data = Model.model_validate(response.json())
    return data.sectors


if __name__ == "__main__":
    main()
