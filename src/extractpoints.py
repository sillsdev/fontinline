#!/usr/bin/env python

import fontforge
import optparse
import argparse
import sys
import os, os.path
import itertools
import shapely
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
    args = parser.parse_args()
    args.svgfilename = args.glyphname + '.svg'
    args.datfilename = args.glyphname + '.dat'
    return args

def savepoints(pointlist, filename=None):
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

def levels(polylines):
    if polylines==[]:
        return []
    polygons=[]
    for i in polylines:
        d=dict()
        d['poly']=Polygon(i)
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

def immediateparent(levels):
    for i, item in enumerate(levels[1:]):
        for polyline in item:
            for parent in polyline['parents']:
                if parent in levels[i]:
                    polyline['immediateparent']=parent
    return levels

def immediatechildren(levels):
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
    padauk = fontforge.open(fname)
    global args
    args.em = padauk.em
    if isinstance(letter, int):
        codepoint = letter
        glyph = padauk[codepoint]
        # Should use args.glyphname for this...
        letter = glyph.glyphname
    if letter.startswith('U+'):
        codepoint = int(glyphname[2:], 16)
        glyph = padauk[codepoint]
        # Should use args.glyphname for this...
        letter = glyph.glyphname
    pa = padauk[letter] # U+1015 MYANMAR LETTER PA
    layer = pa.foreground
    print "U+1015 has {} layer(s)".format(len(layer))
    # Result was 1: so there is exactly one contour. If there were more, we'd
    # loop through them each in turn.
    polylines = []
    holes = []
    for contour in layer:
        points = list(contour)
        pointlist_with_midpoints = extrapolate_midpoints(points)
        vectors = extractvectors(pointlist_with_midpoints)

        #polyline = ff_to_tuple(vectorpairs_to_pointlist(vectors))
        polyline = vectorpairs_to_pointlist(vectors)
        if contour.isClockwise():
            polylines.append(polyline)
        else:
            holes.append(polyline)
    #make_svg(polylines)
    #savepoints(polylines[0])
    #import subprocess
    #subprocess.call(['python', '../../python-poly2tri/test.py', args.datfilename, '0', '0', '0.4'])
    triangles = make_triangles(polylines, holes)
    draw_all(polylines, holes, triangles)
    return points
    # Note that there may be several off-curve points in a sequence, as with
    # the U+1015 example I chose here. The FontForge Python documentation at
    # one point talks about "the TrueType idiom where an on-curve point mid-way
    # between its control points may be omitted, leading to a run of off-curve
    # points (with implied but unspecified on-curve points between them)."

def flip_polyline(polyline):
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
    result = []
    for point in polyline:
        try:
            x, y = point.x, point.y
        except AttributeError:
            x, y = point[0], point[1]
        result.append(p2t.Point(x, y))
    return result

def make_triangles(polylines, holes=None):
    if holes is None:
        holes = []
    triangles = []
    for polyline in polylines:
        new_polyline = convert_polyline_to_polytri_version(polyline)
        del new_polyline[-1]
        cdt = p2t.CDT(new_polyline)
        for hole in holes:
            del hole[-1]
            cdt.add_hole(hole)
        triangles.extend(cdt.triangulate())
    return triangles

def draw_all(polylines, holes, triangles):
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
    ZOOM = 0.5  # Reduce size by half
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
    avgx = (point1.x + point2.x) / 2.0
    avgy = (point1.y + point2.y) / 2.0
    avgpoint = fontforge.point(avgx, avgy, True)
    return avgpoint

def averagepoint_astuple(point1, point2):
    avgx = (point1[0] + point2[0]) / 2.0
    avgy = (point1[1] + point2[1]) / 2.0
    avgpoint = (avgx, avgy)
    return avgpoint

def pairwise(source):
    source2 = itertools.islice(source, 1, None)
    for a, b in itertools.izip(source, source2):
        yield (a, b)

def extrapolate_midpoints(points):
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

def subdividebezier(points,n):
    if n<=0:
        yield "you cannot subdivide into less than one piece"
    if not type(n)==int:
        yield "you cannot subdivide into a non-integer number of pieces"
    i=0
    while i<=n:
        result1 = ((n-i)**2)*points[0][0]+2*i*(n-i)*points[1][0]+i*i*points[2][0]
        result2 = ((n-i)**2)*points[0][1]+2*i*(n-i)*points[1][1]+i*i*points[2][1]
        yield (result1/(n*n),result2/(n*n))
        i=i+1

def extractbeziers(points):
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
            yield candidate
        else:
            yield [candidate[0], candidate[-1]]

def vectorpairs_to_pointlist(pairs):
    pairs = list(pairs)
    return [pair[0] for pair in pairs] + [pairs[-1][-1]]

def ff_to_tuple(ffpointlist):
    return [(p.x, args.em-p.y) for p in ffpointlist]

def polydraw(points):
    polylines = [points]
    make_svg(polylines)

def make_svg(polylines):
    import svgwrite
    svg = svgwrite.Drawing(filename = "tryme.svg")
    for polyline in polylines:
        svgshape = svgwrite.shapes.Polyline(polyline, stroke="black", stroke_width=10, fill="white")
        svg.add(svgshape)
    svg.save()
    import subprocess
    print "About to load inkscape, please wait a bit..."
    subprocess.call(['inkscape', 'tryme.svg'])
    print "Did it work? You tell me, I'm just a computer so I can't tell."

def main():
    global args
    args = parse_args()
    extraction_demo('/usr/share/fonts/truetype/padauk/Padauk.ttf',0xaa75)
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
