# Download sector data from https://travellermap.com

See [The Traveller Map API](https://travellermap.com/doc/api).

## Tasks

### run

```sh
uv run tmdownload.py -vv
```

### run-poster

```sh
uv run tmdownload.py -p
```

### run-db

```sh
uv run tmdownload.py -d
```

### explore-db

```sh
uv run --with datasette datasette out/travellermap.db
```

### format

Formatting & linting

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