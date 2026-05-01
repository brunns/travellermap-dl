# Download sector data from https://travellermap.com

See [The Traveller Map API](https://travellermap.com/doc/api).

## Tasks

These tasks can be run using [xc](https://xcfile.dev/).

### download-all

Download posters and create database

```sh
uv run tmdownload.py -vv -j
```

### download-poster

Download posters

```sh
uv run tmdownload.py -p -vv -j
```

### create-db

Create database

```sh
uv run tmdownload.py -d -vv -j
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
