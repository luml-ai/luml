<a id="luml.experiments.backends._cursor"></a>

# luml.experiments.backends.\_cursor

<a id="luml.experiments.backends._cursor.Cursor"></a>

## Cursor Objects

```python
class Cursor()
```

<a id="luml.experiments.backends._cursor.Cursor.validate_for"></a>

#### validate\_for

```python
def validate_for(sort_by: str, order: str) -> "Cursor | None"
```

<a id="luml.experiments.backends._cursor.Cursor.encode"></a>

#### encode

```python
def encode() -> str
```

<a id="luml.experiments.backends._cursor.Cursor.decode"></a>

#### decode

```python
@classmethod
def decode(cls, cursor_str: str | None) -> "Cursor | None"
```

<a id="luml.experiments.backends._cursor.Cursor.build"></a>

#### build

```python
@classmethod
def build(
    cls,
    items: list[Any],
    limit: int,
    sort_by: str = _CREATED_AT_KEY,
    order: str = "desc",
    json_sort_column: str | None = None
) -> "Cursor | None"
```

<a id="luml.experiments.backends._cursor.Cursor.get_cursor"></a>

#### get\_cursor

```python
@classmethod
def get_cursor(
    cls,
    items: list[Any],
    limit: int,
    sort_by: str = _CREATED_AT_KEY,
    order: str = "desc",
    json_sort_column: str | None = None
) -> str | None
```

<a id="luml.experiments.backends._cursor.Cursor.decode_and_validate"></a>

#### decode\_and\_validate

```python
@classmethod
def decode_and_validate(
    cls,
    cursor_str: str | None,
    sort_by: str,
    order: str
) -> "Cursor | None"
```

