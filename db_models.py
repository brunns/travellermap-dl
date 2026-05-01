from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Milieu(Base):
    __tablename__ = "milieus"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None] = mapped_column()

    sector_data: Mapped[list[Sector]] = relationship(back_populates="milieu")

    def __repr__(self) -> str:
        return f"<Milieu(name='{self.name}', description='{self.description}')>"


class Sector(Base):
    __tablename__ = "sectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    x_coordinate: Mapped[float] = mapped_column()
    y_coordinate: Mapped[float] = mapped_column()
    milieu_id: Mapped[int] = mapped_column(ForeignKey("milieus.id"))

    __table_args__ = (UniqueConstraint("name", "milieu_id"),)

    subsectors: Mapped[list[Subsector]] = relationship(back_populates="sector", cascade="all, delete-orphan")
    milieu: Mapped[Milieu] = relationship(back_populates="sector_data")

    def __repr__(self) -> str:
        return (
            f"<Sector(name='{self.name}', x={self.x_coordinate}, y={self.y_coordinate}, milieu='{self.milieu.name}')>"
        )


class Subsector(Base):
    __tablename__ = "subsectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    index: Mapped[str] = mapped_column()
    sector_id: Mapped[int] = mapped_column(ForeignKey("sectors.id"))

    __table_args__ = (UniqueConstraint("index", "sector_id"),)

    sector: Mapped[Sector] = relationship(back_populates="subsectors")
    worlds: Mapped[list[World]] = relationship(back_populates="subsector", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<Subsector(name='{self.name}', sector='{self.sector.name}', index={self.index}, "
            f"milieu='{self.sector.milieu.name}')>"
        )


class World(Base):
    __tablename__ = "worlds"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    subsector_id: Mapped[int] = mapped_column(ForeignKey("subsectors.id"))
    hex_location: Mapped[str] = mapped_column()
    population_id: Mapped[int] = mapped_column(ForeignKey("populations.id"))
    tech_level_id: Mapped[int] = mapped_column(ForeignKey("tech_levels.id"))
    starport_id: Mapped[int] = mapped_column(ForeignKey("starports.id"))
    size_id: Mapped[int] = mapped_column(ForeignKey("sizes.id"))
    atmosphere_id: Mapped[int] = mapped_column(ForeignKey("atmospheres.id"))
    hydrosphere_id: Mapped[int] = mapped_column(ForeignKey("hydrospheres.id"))
    government_id: Mapped[int] = mapped_column(ForeignKey("governments.id"))
    law_level_id: Mapped[int] = mapped_column(ForeignKey("law_levels.id"))
    trade_codes: Mapped[str | None] = mapped_column()
    zone: Mapped[str] = mapped_column()
    bases: Mapped[str] = mapped_column()

    __table_args__ = (UniqueConstraint("hex_location", "subsector_id"),)

    subsector: Mapped[Subsector] = relationship(back_populates="worlds")
    starport: Mapped[Starport] = relationship()
    size: Mapped[Size] = relationship()
    atmosphere: Mapped[Atmosphere] = relationship()
    hydrosphere: Mapped[Hydrosphere] = relationship()
    population: Mapped[Population] = relationship()
    government: Mapped[Government] = relationship()
    law_level: Mapped[LawLevel] = relationship()
    tech_level: Mapped[TechLevel] = relationship()

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
            f"tech_level='{self.tech_level.name if self.tech_level else None}', "
            f"zone='{self.zone}', "
            f"bases='{self.bases}', "
            ")>"
        )


class Starport(Base):
    """Starport types - see https://wiki.travellerrpg.com/Starport"""

    __tablename__ = "starports"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    value: Mapped[int | None] = mapped_column()
    name: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column()

    def __repr__(self) -> str:
        return f"<Starport(value='{self.value}', name='{self.name}', description='{self.description}')>"


class Size(Base):
    __tablename__ = "sizes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    value: Mapped[int | None] = mapped_column()
    description: Mapped[str | None] = mapped_column()

    def __repr__(self) -> str:
        return f"<Size(value='{self.value}', description='{self.description}')>"


class Atmosphere(Base):
    __tablename__ = "atmospheres"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    value: Mapped[int | None] = mapped_column()
    description: Mapped[str | None] = mapped_column()

    def __repr__(self) -> str:
        return f"<Atmosphere(value='{self.value}', description='{self.description}')>"


class Hydrosphere(Base):
    __tablename__ = "hydrospheres"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    value: Mapped[int | None] = mapped_column()
    description: Mapped[str | None] = mapped_column()

    def __repr__(self) -> str:
        return f"<Hydrosphere(value='{self.value}', description='{self.description}')>"


class Government(Base):
    __tablename__ = "governments"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    value: Mapped[int | None] = mapped_column()
    description: Mapped[str | None] = mapped_column()

    def __repr__(self) -> str:
        return f"<Government(value='{self.value}', description='{self.description}')>"


class LawLevel(Base):
    __tablename__ = "law_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    value: Mapped[int | None] = mapped_column()
    description: Mapped[str | None] = mapped_column()

    def __repr__(self) -> str:
        return f"<LawLevel(value='{self.value}', description='{self.description}')>"


class Population(Base):
    __tablename__ = "populations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    value: Mapped[int | None] = mapped_column()
    description: Mapped[str | None] = mapped_column()

    def __repr__(self) -> str:
        return f"<Population(value='{self.value}', description='{self.description}')>"


class TechLevel(Base):
    __tablename__ = "tech_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    value: Mapped[int | None] = mapped_column()
    name: Mapped[str] = mapped_column()
    imperial: Mapped[str] = mapped_column()
    ce: Mapped[str] = mapped_column()
    remarks: Mapped[str | None] = mapped_column()

    def __repr__(self) -> str:
        return f"<TechLevel(value='{self.value}', name='{self.name}')>"
