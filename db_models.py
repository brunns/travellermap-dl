from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Milieu(Base):
    __tablename__ = "milieus"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)

    sector_data = relationship("Sector", back_populates="milieu")

    def __repr__(self) -> str:
        return f"<Milieu(name='{self.name}', description='{self.description}')>"


class Sector(Base):
    __tablename__ = "sectors"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    x_coordinate = Column(Float, nullable=False)
    y_coordinate = Column(Float, nullable=False)
    milieu_id = Column(Integer, ForeignKey("milieus.id"), nullable=False)

    __table_args__ = (UniqueConstraint("name", "milieu_id"),)

    subsectors = relationship("Subsector", back_populates="sector", cascade="all, delete-orphan")
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

    __table_args__ = (UniqueConstraint("index", "sector_id"),)

    sector = relationship("Sector", back_populates="subsectors")
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
    hex_location = Column(String, nullable=False)
    population_id = Column(Integer, ForeignKey("populations.id"), nullable=False)
    tech_level_id = Column(Integer, ForeignKey("tech_levels.id"), nullable=False)
    starport_id = Column(Integer, ForeignKey("starports.id"), nullable=False)
    size_id = Column(Integer, ForeignKey("sizes.id"), nullable=False)
    atmosphere_id = Column(Integer, ForeignKey("atmospheres.id"), nullable=False)
    hydrosphere_id = Column(Integer, ForeignKey("hydrospheres.id"), nullable=False)
    government_id = Column(Integer, ForeignKey("governments.id"), nullable=False)
    law_level_id = Column(Integer, ForeignKey("law_levels.id"), nullable=False)
    trade_codes = Column(String, nullable=True)
    zone = Column(String, nullable=False)
    bases = Column(String, nullable=False)

    __table_args__ = (UniqueConstraint("hex_location", "subsector_id"),)

    subsector = relationship("Subsector", back_populates="worlds")
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
            f"tech_level='{self.tech_level.name if self.tech_level else None}', "
            f"zone='{self.zone}', "
            f"bases='{self.bases}', "
            ")>"
        )


class Starport(Base):
    """Starport types - see https://wiki.travellerrpg.com/Starport"""

    __tablename__ = "starports"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    value = Column(Integer, nullable=True, unique=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Starport(value='{self.value}', name='{self.name}', description='{self.description}')>"


class Size(Base):
    __tablename__ = "sizes"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    value = Column(Integer, nullable=True, unique=False)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Size(value='{self.value}', description='{self.description}')>"


class Atmosphere(Base):
    __tablename__ = "atmospheres"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    value = Column(Integer, nullable=True, unique=False)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Atmosphere(value='{self.value}', description='{self.description}')>"


class Hydrosphere(Base):
    __tablename__ = "hydrospheres"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    value = Column(Integer, nullable=True, unique=False)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Hydrosphere(value='{self.value}', description='{self.description}')>"


class Government(Base):
    __tablename__ = "governments"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    value = Column(Integer, nullable=True, unique=False)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Government(value='{self.value}', description='{self.description}')>"


class LawLevel(Base):
    __tablename__ = "law_levels"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    value = Column(Integer, nullable=True, unique=False)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<LawLevel(value='{self.value}', description='{self.description}')>"


class Population(Base):
    __tablename__ = "populations"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    value = Column(Integer, nullable=True, unique=False)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Population(value='{self.value}', description='{self.description}')>"


class TechLevel(Base):
    __tablename__ = "tech_levels"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    value = Column(Integer, nullable=True, unique=False)
    name = Column(String, nullable=False)
    imperial = Column(String, nullable=False)
    ce = Column(String, nullable=False)
    remarks = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<TechLevel(value='{self.value}', name='{self.name}')>"
