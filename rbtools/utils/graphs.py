from __future__ import unicode_literals

from collections import defaultdict, deque

import six


def visit_depth_first(graph, start):
    """Yield vertices in the graph starting at the start vertex.

    The vertices are yielded in a depth first order and only those vertices
    that can be reached from the start vertex will be yielded.
    """
    unvisited = deque()
    visited = set()

    unvisited.append(start)

    while unvisited:
        vertex = unvisited.popleft()

        if vertex in visited:
            continue

        visited.add(vertex)

        yield vertex

        if vertex in graph:
            for adjacent in graph[vertex]:
                unvisited.append(adjacent)


def path_exists(graph, start, end):
    """Determine if a directed path exists between start and end in graph."""
    for vertex in visit_depth_first(graph, start):
        if vertex == end:
            return True

    return False


def toposort(graph):
    """Return a topological sorting of the vertices in the directed graph.

    If the graph contains cycles, ValueError is raised.
    """
    result = []

    indegrees = defaultdict(int)  # The in-degree of each vertex in the graph.

    for head in six.iterkeys(graph):
        indegrees[head] = 0

    for tails in six.itervalues(graph):
        for tail in tails:
            indegrees[tail] += 1

    heads = set(
        vertex
        for vertex, indegree in six.iteritems(indegrees)
        if indegree == 0
    )

    while len(heads):
        head = heads.pop()
        result.append(head)

        if head in graph:
            for tail in graph[head]:
                indegrees[tail] -= 1

                if indegrees[tail] == 0:
                    heads.add(tail)

    if any(six.itervalues(indegrees)):
        raise ValueError('Graph contains cycles.')

    return result
