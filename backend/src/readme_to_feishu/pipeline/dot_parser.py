"""Simple DOT parser for Attractor pipeline subset (digraph, nodes, edges, attributes)."""

from __future__ import annotations

import re
from pathlib import Path

from .graph import Edge, Graph, Node


def _strip_comments(text: str) -> str:
    # Line comments
    text = re.sub(r"//[^\n]*", "", text)
    # Block comments
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text


def _parse_value(s: str) -> str | int | float | bool:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\\\", "\\")
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _parse_attr_block(content: str) -> dict:
    """Parse [ key = value , key2 = value2 ] into dict."""
    attrs = {}
    content = content.strip()
    if not content or content == "[]":
        return attrs
    inner = content[1:-1].strip()
    # Simple split by comma, respecting quoted strings
    current = []
    in_quote = False
    for c in inner:
        if c == '"' and (not current or current[-1] != "\\"):
            in_quote = not in_quote
            current.append(c)
        elif c == "," and not in_quote:
            part = "".join(current).strip()
            if "=" in part:
                k, _, v = part.partition("=")
                attrs[k.strip()] = _parse_value(v.strip())
            current = []
        else:
            current.append(c)
    if current:
        part = "".join(current).strip()
        if "=" in part:
            k, _, v = part.partition("=")
            attrs[k.strip()] = _parse_value(v.strip())
    return attrs


def parse_dot(source: str | Path) -> Graph:
    """Parse DOT source into a Graph. Strips comments, supports graph/node/edge attributes."""
    if isinstance(source, Path):
        source = source.read_text(encoding="utf-8")
    text = _strip_comments(source)
    text = text.strip()
    graph = Graph()

    # digraph Name {
    digraph_match = re.match(r"digraph\s+(\w+)\s*\{", text)
    if not digraph_match:
        raise ValueError("Expected digraph Identifier { ... }")
    graph.name = digraph_match.group(1)
    rest = text[digraph_match.end() :].rstrip()
    if rest.endswith("}"):
        rest = rest[:-1]

    node_defaults: dict = {}
    edge_defaults: dict = {}

    # Split into statements (by semicolon or by line for node/edge stmts)
    # We scan for pattern: id [ ... ] or id -> id [ ... ]
    pos = 0
    while pos < len(rest):
        rest = rest[pos:].lstrip()
        if not rest:
            break
        # graph [ ... ]
        g = re.match(r"graph\s*\[(.*?)\]", rest, re.DOTALL)
        if g:
            graph.graph_attrs = _parse_attr_block("[" + g.group(1) + "]")
            graph.goal = str(graph.graph_attrs.get("goal", ""))
            graph.label = str(graph.graph_attrs.get("label", ""))
            pos = g.end()
            continue
        # key = value ;
        decl = re.match(r"(\w+)\s*=\s*([^;]+);?", rest)
        if decl:
            k, v = decl.group(1), decl.group(2).strip()
            graph.graph_attrs[k] = _parse_value(v)
            if k == "goal":
                graph.goal = str(_parse_value(v))
            if k == "label":
                graph.label = str(_parse_value(v))
            pos = decl.end()
            continue
        # node [ ... ]
        nd = re.match(r"node\s*\[(.*?)\]", rest, re.DOTALL)
        if nd:
            node_defaults = _parse_attr_block("[" + nd.group(1) + "]")
            pos = nd.end()
            continue
        # edge [ ... ]
        ed = re.match(r"edge\s*\[(.*?)\]", rest, re.DOTALL)
        if ed:
            edge_defaults = _parse_attr_block("[" + ed.group(1) + "]")
            pos = ed.end()
            continue
        # Node: id [ ... ] or id (find matching ] so quoted content with ] is ok)
        node_start = re.match(r"(\w+)\s*\[", rest)
        if node_start:
            nid = node_start.group(1)
            start_bracket = node_start.end() - 1
            i = node_start.end()
            in_quote = False
            while i < len(rest):
                c = rest[i]
                if c == '"' and (i == 0 or rest[i - 1] != "\\"):
                    in_quote = not in_quote
                elif c == "]" and not in_quote:
                    attr_str = rest[start_bracket : i + 1]
                    attrs = dict(node_defaults)
                    attrs.update(_parse_attr_block(attr_str))
                    if nid not in graph.nodes:
                        graph.nodes[nid] = Node(
                            id=nid,
                            label=str(attrs.get("label", nid)),
                            shape=str(attrs.get("shape", "box")),
                            type=str(attrs.get("type", "")),
                            prompt=str(attrs.get("prompt", "")),
                            attrs=attrs,
                        )
                    pos = i + 1
                    break
                i += 1
            else:
                pos = len(rest)
            continue
        # Edge: id -> id [ ... ] or id -> id (try before node_bare so "start -> x" is not consumed as node "start")
        edge_match = re.match(r"(\w+)\s*->\s*(\w+)(\s*\[(.*?)\])?;?", rest, re.DOTALL)
        if edge_match:
            from_id = edge_match.group(1)
            to_id = edge_match.group(2)
            attr_str = edge_match.group(4)
            attrs = dict(edge_defaults)
            if attr_str:
                attrs.update(_parse_attr_block("[" + attr_str + "]"))
            graph.edges.append(
                Edge(
                    from_node=from_id,
                    to_node=to_id,
                    label=str(attrs.get("label", "")),
                    condition=str(attrs.get("condition", "")),
                    weight=int(attrs.get("weight", 0)),
                )
            )
            pos = edge_match.end()
            # Chained edges: A -> B -> C [label="x"] means A->B and B->C both get [label="x"]
            rest_check = rest[pos:].lstrip()
            while re.match(r"->\s*\w+", rest_check):
                next_arrow = re.match(r"->\s*(\w+)(\s*\[(.*?)\])?;?", rest_check, re.DOTALL)
                if next_arrow:
                    from_id = to_id
                    to_id = next_arrow.group(1)
                    graph.edges.append(
                        Edge(
                            from_node=from_id,
                            to_node=to_id,
                            label=str(attrs.get("label", "")),
                            condition=str(attrs.get("condition", "")),
                            weight=int(attrs.get("weight", 0)),
                        )
                    )
                    pos += next_arrow.end()
                    rest_check = rest[pos:].lstrip()
                else:
                    break
            continue
        # Node without attrs: id ;
        node_bare = re.match(r"(\w+)\s*;?\s*", rest)
        if node_bare:
            nid = node_bare.group(1)
            if nid not in graph.nodes:
                attrs = dict(node_defaults)
                graph.nodes[nid] = Node(
                    id=nid,
                    label=str(attrs.get("label", nid)),
                    shape=str(attrs.get("shape", "box")),
                    type=str(attrs.get("type", "")),
                    prompt=str(attrs.get("prompt", "")),
                    attrs=attrs,
                )
            pos = node_bare.end()
            continue
        pos += 1
    return graph
