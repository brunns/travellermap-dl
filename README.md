# Download sector data from https://travellermap.com/

See [The Travelelr Map API](https://travellermap.com/doc/api).

## Tasks

### run

```sh
uv run tmdownload.py -vv
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
```