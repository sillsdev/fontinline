#!/usr/bin/env python

from __future__ import division, print_function
from generalfuncs import ux, uy, are_points_equal
from dataconvert import convert_polyline_to_polytri_version, import_p2t, triangle2threepoints
import sys
import fileinput

def make_triangles(polyline, holes = None):
    """This function takes a dictionary, and an optional holes parameter
    that determines the holes of a polyline, and tesselates the polyline
    into triangles. This is an intermediate step to calculating the midpoints"""
    if holes is None:
        holes = []
    p2t = import_p2t()
    triangles = []
    new_polyline = convert_polyline_to_polytri_version(polyline)
    if are_points_equal(new_polyline[-1], new_polyline[0]):
        del new_polyline[-1]
    cdt = p2t.CDT(new_polyline)
    for hole in holes:
        if are_points_equal(hole[-1], hole[0]):
            del hole[-1]
        hole = convert_polyline_to_polytri_version(hole)
        cdt.add_hole(hole)
    triangles.extend(cdt.triangulate())
    return list(triangle2threepoints(t) for t in triangles)

def parse_input():
    result = []
    points = []
    for line in fileinput.input():
        line = line.strip().lstrip('(').rstrip(')')
        if line == "HOLE:":
            result.append(points)
            points = []
        parts = line.split(",", 1)
        if len(parts) < 2:
            # Skip bad input line
            continue
        x = float(parts[0])
        y = float(parts[1])
        points.append((x,y))
    if len(points) > 0:
        result.append(points)
    return result

def main(argv):
    line_and_holes = parse_input()
    if len(line_and_holes) < 1:
        return 1  # No data received!
    line = line_and_holes[0]
    holes = line_and_holes[1:]
    result = make_triangles(line, holes)
    for triangle in result:
        print(triangle)

if __name__ == '__main__':
    retcode = main(sys.argv)
    sys.exit(retcode)
