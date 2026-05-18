# 02 · Data Model

Four dataclasses make up the core: `Node`, `Tree`, `Action`, and
`EditScript`. They live under `src/core/`.

## `Node` (`src/core/node.py`)

A single class for both interior and leaf nodes; the `kind` field
discriminates.

```python
@dataclass
class Node:
    kind:      Literal["structural", "leaf"]
    label:     str
    children:  list[Node]      # only meaningful for structural
    value:     Any             # leaf payload (None for structural)
    type:      LeafType | None # "number" | "percent" | … | "distribution"
    raw:       str | None      # original wikitext, kept for audit
    unit:      str | None      # e.g. "USD", "km2"
    trend:     int | None      # +1 / 0 / -1 from {{increase}}/{{steady}}/{{decrease}}
    taxonomy:  str | None      # "religion" | "language" | … (for type="distribution")
    parent:    Node | None     # back-pointer; excluded from equality
```

### Leaf types

```
number | percent | year | date | currency | coordinates |
wikilink | text | distribution | empty
```

Leaf payload conventions:

| `type` | `value` representation |
|---|---|
| `number` | `float` |
| `percent` | `float` in `[0, 100]` |
| `year` | `int` (BCE negative) |
| `date` | `datetime.date` |
| `currency` | `float` USD-equivalent; `unit` = original ISO code (e.g. `"USD"`) |
| `coordinates` | `(lat: float, lon: float)` |
| `wikilink` | `str` (resolved entity name) |
| `text` | `str` |
| `distribution` | `list[{path: list[str], weight: float}]` — chips ordered by weight desc |

### Constructors

- `Node.structural(label, children=None)` — wires `parent` of each child.
- `Node.leaf(label, value, type, *, raw=None, unit=None, trend=None, taxonomy=None)`.

### Methods of note

- `walk()` — pre-order generator.
- `postorder()` — post-order generator.
- `add_child / insert_child / remove_child` — mutate structural nodes.
- `value_equals(other)` — compares labels, values, types, taxonomy, unit
  (the things that matter for "did this leaf change?").
- `copy()` — deep copy of the subtree.

## `Tree` (`src/core/tree.py`)

Wraps a root `Node` and offers path-based access.

```python
@dataclass
class Tree:
    root: Node
    name: str | None
```

- **Paths**: `NodePath = tuple[int, ...]`. `tree.get((1, 0))` returns
  `tree.root.children[1].children[0]`. `tree.path_of(node)` walks
  parent pointers back to the root.
- **Dotted lookup**: `tree.find_by_label("economy.gdp_ppp.value")`.
- **Traversal**: `tree.walk()`, `tree.postorder()`, `tree.leaves()`.
- **Pretty-print**: `tree.to_ascii()` — used in tests / debugging.

`__post_init__` re-wires parent pointers defensively so callers can
build a node graph anywhere and then drop it into a `Tree`.

## `Action` (`src/core/action.py`)

A single edit operation.

```python
@dataclass
class Action:
    op:       Literal["insert", "delete", "relabel"]
    path:     tuple[int, ...]    # target path (or parent path for insert)
    cost:     float
    new_node: Node | None        # replacement / inserted subtree
    position: int | None         # child index for insert
    # captured at script-build time so the script is reversible/auditable:
    old_label:    str | None
    old_value:    object
    old_type:     str | None
    old_taxonomy: str | None
```

The three operation semantics:

- **insert** — insert `new_node` as child `position` of the node at `path`.
- **delete** — remove the subtree rooted at `path`.
- **relabel** — replace the payload of the node at `path` with
  `new_node`'s payload (label / value / type / unit / trend /
  taxonomy). Structure (children) is unaffected.

## `EditScript` (`src/core/edit_script.py`)

```python
@dataclass
class EditScript:
    operations:  list[Action]
    total_cost:  float
    source_name: str | None
    target_name: str | None
    mapping:     list[tuple[tuple[int,...], tuple[int,...]]]
```

`mapping` is the algorithm's node-pair correspondence between source and
target, where each entry is `(t1_path, t2_path)`. The frontend uses it
to color the diff consistently on *both* trees from a single source of
truth.

### `EditScript.apply(tree) → Tree`

Returns a new tree (input is not mutated). Application order:

1. **Relabels** first — they don't change shape.
2. **Deletes**, sorted `(len(path), path) reverse` so deepest +
   rightmost is processed first. This guarantees that index paths of
   not-yet-deleted nodes remain valid.
3. **Inserts**, sorted `(len(path), path, position) ascending` so
   shallowest + leftmost + smallest position is processed first.
   Parents must exist before children.

### `EditScript.inverse() → EditScript`

Returns the script that undoes this one (target → source). Each
operation is inverted using its captured `old_*` fields. Deletes can
only be inverted if `new_node` (the deleted subtree) was preserved at
script-build time; both algorithms do this.

### JSON round-trip

`to_dict()` / `from_dict()` and `to_json(path)` / `from_json(path)`.

- `datetime.date` → ISO string (Mongo can't encode `date` directly,
  only `datetime`).
- Tuples → lists. The deserializer rebuilds `date` and tuple
  coordinates from the type hint on each leaf.
- The `mapping` field is preserved.

### Invariants

- A relabel's `path` is a path in the *source* tree as it was at
  script-build time. Relabels don't change shape, so paths stay valid.
- A delete's `path` is a path in the *original source tree*, not the
  mutated working copy. The apply-time sort order keeps these paths
  valid.
- An insert's `path` is the parent path in the source tree **after
  all deletes have been applied** — the script-builder simulates the
  deletes during emission so the captured path matches what
  `apply()` will see.
