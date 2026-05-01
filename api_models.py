from __future__ import annotations

from pydantic import BaseModel, Field


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
