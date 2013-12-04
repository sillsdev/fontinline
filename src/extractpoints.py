#!/usr/bin/env python

import fontforge
import optparse
import argparse
import sys
import os, os.path
import itertools
import shapely
import warnings
from shapely.geometry.polygon import Polygon
sys.path.append('../../python-poly2tri')
import p2t
sys.path.remove('../../python-poly2tri')

DEFAULT_FONT='/usr/share/fonts/truetype/padauk/Padauk.ttf'
DEFAULT_GLYPH='u1021'

def parse_args():
    "Parse the arguments the user passed in"
    parser = argparse.ArgumentParser(description="Demonstrate parsing arguments")
    #parser.add_argument('--help', help="Print the help string")
    parser.add_argument('-v', '--verbose', action="store_true", help="Give more verbose error messages")
    parser.add_argument("inputfilename", nargs="?", default=DEFAULT_FONT, help="Font file (SFD or TTF format)")
    parser.add_argument("glyphname", nargs="?", default=DEFAULT_GLYPH, help="Glyph name to extract")
    parser.add_argument('-z', '--zoom', action="store", type=float, default=1.0, help="Zoom level (default 1.0)")
    args = parser.parse_args()
    args.svgfilename = args.glyphname + '.svg'
    args.datfilename = args.glyphname + '.dat'
    return args

def savepoints(pointlist, filename=None):
    """Saves the points to a file that is called f. Also makes sure starting point is not equal to ending point
    This function accepts a list of tuples"""
    if pointlist[0] == pointlist[-1]:
        del pointlist[-1]
    if filename is None:
        filename = args.datfilename
    f = file(filename, 'w')
    for point in pointlist:
        try:
            x, y = point.x, point.y
        except AttributeError:
            x, y = point[0], point[1]
        f.write("{} {}\n".format(x,y))
    f.close()

# Demo of how to extract the control points from a font.
# Run "sudo apt-get install fonts-sil-padauk" before calling this function.
# Extending this function to arbitrary fonts and glyphs is left as an exercise
# for the reader. ;-)

def calculate_parents(polylines):
    """This function takes a list of fontforge points and turns it into a list of dictionaries.
    Each dictionary has the polygon, the list of points, the children (the polygons inside the
    given polygon, and the parents (the polygons containing the given polygon)"""
    if polylines==[]:
        return []
    polygons=[]
    for i in polylines:
        d=dict()
        d['poly']=Polygon(ff_to_tuple(i))
        d['line']=i
        d['children']=[]
        d['parents']=[]
        polygons.append(d)
    for a,b in itertools.permutations(polygons,2):
        if a['poly'].within(b['poly']):
            a['parents'].append(b)
            b['children'].append(a)
    return polygons

def levels(polygons):
    """This function takes a list of dictionaries from the parentsandchildren function
    and turns it into a list of lists of dictionaries. Each inner list is the list of
    the dictionaries corresponding to the polylines at the level of the index of the list."""
    maxdepth=-1
    for item in polygons:
        item['level']=len(item['parents'])
        maxdepth=max(maxdepth,item['level'])
    result=[]
    #result should go from 0 to maxdepth inclusive.
    for i in range(maxdepth+1):
        result.append([])
    for i in polygons:
        result[i['level']].append(i)
    return result

def calculateimmediateparent(levels):
    """This function takes a list of lists of dictionaries given by the levels function
    and adds the key "immediate parents" to each of the dictionaries, which gives the
    innermost polyline containing the given polyline"""
    for i, item in enumerate(levels[1:]):
        for polyline in item:
            for parent in polyline['parents']:
                if parent in levels[i]:
                    polyline['immediateparent']=parent
    return levels

def calculateimmediatechildren(levels):
    """This function takes a list of lists of dictionaries given by the levels function
    and adds the key "immediate children" to each of the dictionaries, which gives the
    outermost polyline inside the given polyline"""
    for i, item in enumerate(levels):
        if i==len(levels)-1:
            break
        for polyline in item:
            polyline['immediatechildren']=[]
            for child in polyline['children']:
                if child in levels[i+1]:
                    polyline['immediatechildren'].append(child)
    return levels

def extraction_demo(fname,letter):
    font = fontforge.open(fname)
    global args
    args.em = font.em
    if isinstance(letter, int):
        codepoint = letter
    elif letter.startswith('U+'):
        codepoint = int(letter[2:], 16)
    else:
        codepoint = letter
    glyph = font[codepoint]
    layer = glyph.foreground
    print "{} has {} layer{}".format(args.glyphname, len(layer), ('' if len(layer) == 1 else 's'))
    # Result was 1: so there is exactly one contour. If there were more, we'd
    # loop through them each in turn.
    polylines = []
    triangles = []
    #holes = []
    for contour in layer:
        points = list(contour)
        pointlist_with_midpoints = extrapolate_midpoints(points)
        vectors = extractvectors(pointlist_with_midpoints)

        #polyline = ff_to_tuple(vectorpairs_to_pointlist(vectors))
        polyline = vectorpairs_to_pointlist(vectors)
        polylines.append(polyline)  # This includes "real" polys and holes, both
    parent_data = calculate_parents(polylines)
    level_data = levels(parent_data)
    level_data = calculateimmediatechildren(level_data)
    for level in level_data[::2]:
        for poly in level:
            triangles.extend(make_triangles(poly, poly.get('immediatechildren', [])))
        #if contour.isClockwise():
            #polylines.append(polyline)
        #else:
            #holes.append(polyline)
    #savepoints(polylines[0])
    #import subprocess
    #subprocess.call(['python', '../../python-poly2tri/test.py', args.datfilename, '0', '0', '0.4'])
    #triangles = make_triangles(polylines, holes)
    draw_all(polylines, [], triangles)
    return points
    # Note that there may be several off-curve points in a sequence, as with
    # the U+1015 example I chose here. The FontForge Python documentation at
    # one point talks about "the TrueType idiom where an on-curve point mid-way
    # between its control points may be omitted, leading to a run of off-curve
    # points (with implied but unspecified on-curve points between them)."

def flip_polyline(polyline):
    """This function takes a list of tuples (the polyline), and inverts the y coordinate of each point
    because the coordinate systems for fontforge are different than the coordinate systems for the p2t program."""
    result = []
    for point in polyline:
        try:
            x, y = point.x, args.em-point.y
            result.append(point.__class__(x,y))
        except AttributeError:
            x, y = point[0], args.em-point[1]
            result.append(tuple(x,y))
    return result

def convert_polyline_to_polytri_version(polyline):
    """Converts points to p2t points that poly2tri can deal with
    This function accepts tuples or fontforge points"""
    result = []
    for point in polyline:
        try:
            x, y = point.x, point.y
        except AttributeError:
            x, y = point[0], point[1]
        result.append(p2t.Point(x, y))
    return result

def are_points_equal(a, b, epsilon=1e-9):
    """Compares points a and b and returns true if they're equal.

    "Equal", here, is defined as "the difference is less than epsilon" since
    we're dealing with floats.

    Points a and b can be either Fontforge point objects, or tuples."""
    try:
        x1, y1 = a.x, a.y
        x2, y2 = b.x, b.y
    except AttributeError:
        x1, y1 = a[0], a[1]
        x2, y2 = b[0], b[1]
    return (abs(x1-x2) < epsilon) and (abs(y1-y2) < epsilon)

def make_triangles(polygon_data, holes=None):
    """This function takes a dictionary, and an optional holes parameter
    that determines the holes of a polyline, and tesselates the polyline
    into triangles. This is an intermediate step to calculating the midpoints"""
    if holes is None:
        holes = []
    triangles = []
    new_polyline = convert_polyline_to_polytri_version(polygon_data['line'])
    if are_points_equal(new_polyline[-1], new_polyline[0]):
        del new_polyline[-1]
    cdt = p2t.CDT(new_polyline)
    for hole_data in holes:
        hole = hole_data['line']
        if are_points_equal(hole[-1], hole[0]):
            del hole[-1]
        cdt.add_hole(hole)
    triangles.extend(cdt.triangulate())
    return triangles

def draw_all(polylines, holes, triangles):
    """This function takes the list of polylines and holes and the triangulation, and draws it in pygame.
    This function is pending deprecation."""
    import pygame
    from pygame.gfxdraw import trigon, line
    from pygame.locals import *
    SCREEN_SIZE = (1280,800)
    pygame.init()
    screen = pygame.display.set_mode(SCREEN_SIZE,0,8)
    pygame.display.set_caption('Triangulation of glyph (name goes here)')
    red = pygame.Color(255, 0, 0)
    green = pygame.Color(0, 255, 0)
    blue = pygame.Color(0, 0, 255)
    global args
    ZOOM = args.zoom
    for t in triangles:
        x1 = int(t.a.x * ZOOM)
        y1 = int((args.em-t.a.y) * ZOOM)
        x2 = int(t.b.x * ZOOM)
        y2 = int((args.em-t.b.y) * ZOOM)
        x3 = int(t.c.x * ZOOM)
        y3 = int((args.em-t.c.y) * ZOOM)
        trigon(screen, x1, y1, x2, y2, x3, y3, red)

    # Close the polylines loop again prior to drawing
    for polyline in polylines:
        polyline.append(polyline[0])
        flipped = flip_polyline(polyline)
        for a, b in pairwise(flipped):
            x1 = int(a.x * ZOOM)
            y1 = int(a.y * ZOOM)
            x2 = int(b.x * ZOOM)
            y2 = int(b.y * ZOOM)
            line(screen, x1, y1, x2, y2, green)

    # Same for holes
    for hole in holes:
        hole.append(hole[0])
        flipped = flip_polyline(hole)
        for a, b in pairwise(flipped):
            x1 = int(a.x * ZOOM)
            y1 = int(a.y * ZOOM)
            x2 = int(b.x * ZOOM)
            y2 = int(b.y * ZOOM)
            line(screen, x1, y1, x2, y2, blue)

    # Show result and wait for keypress
    pygame.display.update()
    done = False
    while not done:
        e = pygame.event.wait()
        if (e.type == QUIT):
            done = True
            break
        elif (e.type == KEYDOWN):
            done = True
            break


def averagepoint(point1, point2):
    """This function takes two fontforge points, and finds the average of them"""
    avgx = (point1.x + point2.x) / 2.0
    avgy = (point1.y + point2.y) / 2.0
    avgpoint = fontforge.point(avgx, avgy, True)
    return avgpoint

def averagepoint_astuple(point1, point2):
    """This function takes two tuples, and returns the average of them"""
    avgx = (point1[0] + point2[0]) / 2.0
    avgy = (point1[1] + point2[1]) / 2.0
    avgpoint = (avgx, avgy)
    return avgpoint

def pairwise(source):
    """This funcion takes any iterable [a,b,c,d,...], and returns an iterator which yields (a,b), (b,c), (c,d)..."""
    source2 = itertools.islice(source, 1, None)
    for a, b in itertools.izip(source, source2):
        yield (a, b)

def extrapolate_midpoints(points):
    """This function takes a list of fontforge points and if two consecutive points are off-curve
    it extrapolates the on-curve point between them."""
    if not (points[-1] == points[0]):
        points.append(points[0])  # Close the curve
    result = []
    for a, b in pairwise(points):
        if a.on_curve or b.on_curve:
            # No need to extrapoalate for this pair
            result.append(a)
        else:
            midpoint = averagepoint(a, b)
            result.append(a)
            result.append(midpoint)
    # Last point will not have been part of any pairs, so it won't have been
    # appended. Append it now.
    result.append(points[-1])
    return result

def subdivideline(points,n):
    """This function takes a list of tuples or lists and finds n-1 evenly spaced points (tuples)
    along the line that connects them in between the two points"""
    if n<=0:
        raise ValueError("you cannot subdivide into less than one piece")
    if not type(n)==int:
        raise ValueError("you cannot subdivide into a non-integer number of pieces")
    i=0
    while i<=n:
        result1=(n-i)*points[0].x+i*points[1].x
        result2=(n-i)*points[0].y+i*points[1].y
        yield fontforge.point(result1/n,result2/n, True)
        i=i+1

def subdividebezier(points,n):
    """This function takes three points (tuples), and yields n-1 evenly spaced
    points (tuples) along the bezier defined by those points"""
    if n<=0:
        raise ValueError("you cannot subdivide into less than one piece")
    if not type(n)==int:
        raise ValueError("you cannot subdivide into a non-integer number of pieces")
    i=0
    while i<=n:
        result1 = ((n-i)**2)*points[0].x+2*i*(n-i)*points[1].x+i*i*points[2].x
        result2 = ((n-i)**2)*points[0].y+2*i*(n-i)*points[1].y+i*i*points[2].y
        yield fontforge.point(result1/(n*n),result2/(n*n),True)
        i=i+1

def extractbeziers(points):
    """This function takes a list of fontforge points and yields lists that contain single lines or beziers."""
    i=0
    while i<len(points)-1:
        # This appends a list of the two consecutive on-curve points with any off-curve points between them.
        if points[i+1].on_curve:
            added_bezier=points[i:i+2]
            i=i+1
        else:
            added_bezier=points[i:i+3]
            i=i+2
        yield added_bezier

def extractvectors(points):
    points = list(points)
    for candidate in extractbeziers(points):
        if len(candidate) == 2:
            # It's a vector
            subdivided=subdivideline(candidate,10)
            for v in pairwise(subdivided):
                yield v
        else:
            #change this to variable later
            subdivided=subdividebezier(candidate,10)
            for v in pairwise(subdivided):
                yield v

def vectorpairs_to_pointlist(pairs):
    """This function takes a list of pairs of points and turns it into a single list of points.
    This function needs to be updated when we subdivide bezier curves"""
    pairs = list(pairs)
    if not pairs:
        return []
    return [pair[0] for pair in pairs] + [pairs[-1][-1]]

def ff_to_tuple(ffpointlist):
    """This function takes a list of fontforge points and turns it into a list of tuples.
    This function needs to be updated to retain the oncurve-offcurve information"""
    return [(p.x, p.y) for p in ffpointlist]

def main():
    """This is the main function we use that calls extraction_demo and also runs
    a sanity check to make sure everything works properly."""
    global args
    args = parse_args()
    extraction_demo(args.inputfilename, args.glyphname)
    #extraction_demo('/usr/share/fonts/truetype/padauk/Padauk.ttf',0xaa75)
    #extraction_demo('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',0x0e3f)
    return 0

if __name__ == "__main__":
    retcode=main()
    if retcode!=0:
        sys.exit(retcode)

#    if not os.path.exists(opts.inputfilenamappend(e):
#        print "File {} not found or not accessible".format(opts.inputfilename)
#        sys.exit(2)
#    font = fontforge.open(opts.inputfilename)
#    font[opts.glyphname].export(opts.exportname)
#    font.close()
