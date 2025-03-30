# Download sector data from https://travellermap.com

See [The Traveller Map API](https://travellermap.com/doc/api).

## Tasks

### download-all

Download posters and create database

```sh
uv run tmdownload.py -vv
```

### download-poster

Download posters

```sh
uv run tmdownload.py -p -vv
```

### create-db

Create database

```sh
uv run tmdownload.py -d -vv
```

### explore-db

Explore database

```sh
uv run --with datasette datasette out/travellermap.db -o
```

### format

Fix formatting etc.

```sh
uv run --with ruff ruff format
uv run --with ruff ruff check --fix-only
```

### lint

Check formatting & other linting.

```sh
uv run --with ruff ruff format --check
uv run --with ruff ruff check 
uv run --with pyright pyright
```