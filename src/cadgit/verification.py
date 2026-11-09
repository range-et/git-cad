"""Bounded per-call verification of immutable revision graphs."""
from collections import defaultdict

from .errors import CadgitError


def verify_dependencies(project, record, library=False, ancestors=()):
    from .library import Library

    assets = Library(project)
    indexes = {}
    nodes = {}
    records_by_key = {}
    edges = []
    active = set()
    completed = set()
    root = ('library' if library else 'record', record['id'])
    pending = [(root, record, False)]
    seeded = set(ancestors or ())

    def resolve(kind, revision):
        if kind not in indexes:
            if kind == 'library':
                records = assets.records() + assets.legacy()
            elif kind == 'material':
                records = project.records('materials', strict=False)
            else:
                records = project.records(strict=False) + project.records('assemblies', strict=False)
            index = defaultdict(list)
            for item in records:
                index[item['id']].append(item)
            indexes[kind] = index
        matches = indexes[kind].get(revision, [])
        if len(matches) != 1:
            raise CadgitError('Missing, ambiguous or unreadable exact revision: ' + revision)
        return matches[0]

    while pending:
        key, current, exiting = pending.pop()
        if exiting:
            active.remove(key)
            completed.add(key)
            continue
        if key in active or key[1] in seeded:
            nodes.setdefault(key, []).append('Cyclic revision dependency')
            continue
        if key in completed:
            continue
        try:
            if current is None:
                current = resolve(*key)
            records_by_key[key]=current
            errors, links = project._verify_local(current)
            if key[0] == 'library':
                extra, library_links = assets._verify_local(current)
                errors.extend(extra)
                links.extend(library_links)
        except CadgitError as exc:
            nodes[key] = [str(exc)]
            completed.add(key)
            continue
        nodes[key] = errors
        active.add(key)
        pending.append((key, current, True))
        for kind, revision, role in reversed(links):
            if not isinstance(revision,str) or not revision:
                errors.append('Invalid '+role+' revision reference')
                continue
            target = (kind, revision)
            edges.append((key, target, role))
            pending.append((target, None, False))

    # Propagate invalidity once per node/edge, without recursively duplicating
    # errors across diamond-shaped histories. Keep every affected role visible.
    for parent, child, role in edges:
        if role=="parent" and child[0]=="scene" and child in records_by_key:
            target=records_by_key[child]
            if not target["id"].startswith("snap_") or target.get("source")!=records_by_key[parent].get("source"):
                nodes[parent].append("Save parent must be a snapshot of the same source: "+child[1])
    parents = defaultdict(set)
    for parent, child, _ in edges:
        parents[child].add(parent)
    invalid = {key for key, errors in nodes.items() if errors}
    queue = list(invalid)
    while queue:
        for parent in parents[queue.pop()]:
            if parent not in invalid:
                invalid.add(parent)
                queue.append(parent)
    errors = []
    for key, failures in nodes.items():
        errors.extend((('' if key == root else key[1] + ': ') + error) for error in failures)
    for parent, child, role in dict.fromkeys(edges):
        if child in invalid:
            errors.append(role + ' ' + child[1] + ': dependency integrity failed')
    return {'id': record['id'], 'ok': not errors, 'errors': errors}
