from __future__ import division, print_function

"""Library for converting lines and polygons between various formats

Formats used in our code:
    polyline - a list of (x, y) tuples.
    ffpointlist - a list of FontForge Point objects (with .x and .y attributes)
    LineString - a shapely.geometry.LineString object
        linestring.coords acts like a list of (x, y) tuples
    Polygon - a shapely.geometry.Polygon object
        polygon.exterior is a LinearRing (like a closed LineString) of the outside
        polygon.interiors is a list of LinearRings, one per "hole"
        In both cases, use coords to get lists of tuples, e.g.:
            polygon.exterior.coords
            (hole.coords for hole in polygon.interiors)
"""

from shapely.geometry import Point, LineString, Polygon
import itertools
import sys, os
from generalfuncs import pairwise, ux, uy

def import_p2t():
    """Find and import the p2t module, which might be in several possible locations:
         * The current directory, or any ancestor directory
         * A "python-poly2tri" directory based of the current dir or an ancestor
    """
    try:
        import p2t
    except ImportError:
        pass  # Rest of function will hunt for it
    else:
        # Found it already, so just return it
        return p2t
    fname = 'p2t.so'
    curdir = os.path.dirname(os.path.abspath(__file__))
    def check(path):
        return os.path.exists(os.path.join(path, fname))
    while True:
        # Check both current dir and python-poly2tri folder
        found = check(curdir)
        if found:
            sys.path.append(curdir)
            import p2t
            sys.path.remove(curdir)
            return p2t
        poly2tri_dir = os.path.join(curdir, 'python-poly2tri')
        found = check(poly2tri_dir)
        if found:
            sys.path.append(poly2tri_dir)
            import p2t
            sys.path.remove(poly2tri_dir)
            return p2t
        parent = os.path.abspath(os.path.join(curdir, '..'))
        if parent == curdir:
            sys.stderr.write("ERROR: python-poly2tri library not found. Please install it from\n")
            sys.stderr.write("https://github.com/hansent/python-poly2tri and follow its build\n")
            sys.stderr.write("instructions to produce the p2t.so file, then copy p2t.so into\n")
            sys.stderr.write("the same folder that contains extractpoints.py.\n")
            raise ImportError, "Could not find python-poly2tri module"
        curdir = parent
        continue
    return p2t # Should never reach here, but just in case

p2t = import_p2t()

def any_to_polyline(pointlist):
    """Given a point list in any format, convert it to a polyline."""
    if hasattr(pointlist, 'exterior'):
        # It's a Polygon; just return the *outside* line
        return pointlist.exterior.coords
    elif hasattr(pointlist, 'coords'):
        # It's a LineString or LinearRing
        return pointlist.coords
    else:
        # It might be a generator
        pointlist = list(pointlist)
        if not pointlist:
            # It's an empty list
            return []
        elif hasattr(pointlist[0], 'x'):
            # It's a list of FontForge (or p2t) points
            return [(p.x, p.y) for p in pointlist]
        else:
            # It was already a list of tuples
            return pointlist

def any_to_closedpolyline(pointlist):
    line = list(any_to_polyline(pointlist))
    if line[0] != line[-1]:
        line.append(line[0])
    return line

def any_to_linestring(pointlist):
    try:
        return LineString(any_to_polyline(pointlist))
    except ValueError:
        print(str(list(pointlist)))
        raise

def any_to_polygon(outside, holes):
    outside = any_to_polyline(outside)
    holes = map(any_to_polyline, holes)
    return Polygon(outside, holes)

def convert_polyline_to_polytri_version(polyline):
    """Converts points to p2t points that poly2tri can deal with
    This function accepts tuples or fontforge points"""
    result = []
    if hasattr(polyline, 'coords'):
        polyline = polyline.coords
    for point in polyline:
        x, y = ux(point), uy(point)
        result.append(p2t.Point(x, y))
    return result

def vectorpairs_to_pointlist(pairs):
    """This function takes a list of pairs of points and turns it into a
    list of lists of points. Each list will be a slice of the points such
    that none of the pairs of consecutive points were not in pairs. The
    number of lists should be equal to the number of pairs removed."""
    pairs = list(pairs)
    if not pairs:
        return []
    return [pair[0] for pair in pairs] + [pairs[-1][-1]]

def vectorpairs_to_linestring(pairs):
    """This function takes a list of pairs of points and turns it into a single LineString."""
    points = list(vectorpairs_to_pointlist(pairs))
    if points[0] == points[-1]:
        del points[-1]
    return any_to_linestring(points)

def get_triangle_point(t, pnum):
    "Get point N of a triangle, no matter the triangle's input format"
    is_tuple = False
    try:
        t.a
    except AttributeError:
        is_tuple = True
    if (is_tuple):
        return t[pnum]
    else:
        if pnum == 0:   return t.a
        elif pnum == 1: return t.b
        elif pnum == 2: return t.c
        else: return t.a

def triangle2threepoints(t):
    a = get_triangle_point(t, 0)
    b = get_triangle_point(t, 1)
    c = get_triangle_point(t, 2)
    return [(ux(a), uy(a)), (ux(b), uy(b)), (ux(c), uy(c))]

def triangle2lines(t):
    a = get_triangle_point(t, 0)
    b = get_triangle_point(t, 1)
    c = get_triangle_point(t, 2)
    l1 = [p2ft(a), p2ft(b)]
    l2 = [p2ft(b), p2ft(c)]
    l3 = [p2ft(c), p2ft(a)]
    return [l1, l2, l3]

def p2ft(point):
    """Converts a point into a representation using a tuple of float objects."""
    try:
        x, y = point.x, point.y
    except AttributeError:
        x, y = point[0], point[1]
    return (x, y)

if __name__ == '__main__':
    sys.stderr.write('Please run extractpoints.py, not this file.\n')
