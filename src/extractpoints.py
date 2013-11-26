#!/usr/bin/env python

import fontforge
import optparse
import argparse
import sys
import os, os.path
import itertools

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
    args.exportname = args.glyphname + '.svg'
    return args

# Demo of how to extract the control points from a font.
# Run "sudo apt-get install fonts-sil-padauk" before calling this function.
# Extending this function to arbitrary fonts and glyphs is left as an exercise
# for the reader. ;-)
def extraction_demo(fname,letter):
    pointlist=[]
    padauk = fontforge.open(fname)
    pa = padauk[letter] # U+1015 MYANMAR LETTER PA
    layer = pa.foreground
    print "U+1015 has {} layer(s)".format(len(layer))
    # Result was 1: so there is exactly one contour. If there were more, we'd
    # loop through them each in turn.
    polylines = []
    for contour in layer:
        points = list(contour)
        pointlist_with_midpoints = extrapolate_midpoints(points)
        vectors = extractvectors(pointlist_with_midpoints)

        polyline = ff_to_tuple(vectorpairs_to_pointlist(vectors))
        polylines.append(polyline)
    make_svg(polylines)
    return points
    # Note that there may be several off-curve points in a sequence, as with
    # the U+1015 example I chose here. The FontForge Python documentation at
    # one point talks about "the TrueType idiom where an on-curve point mid-way
    # between its control points may be omitted, leading to a run of off-curve
    # points (with implied but unspecified on-curve points between them)."

def averagepoint(point1, point2):
    avgx = (point1.x + point2.x) / 2.0
    avgy = (point1.y + point2.y) / 2.0
    avgpoint = fontforge.point(avgx, avgy, True)
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
    return [(p.x, p.y) for p in ffpointlist]

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


if __name__ == "__main__":
    #args = parse_args()  # Not yet used
    extraction_demo('/usr/share/fonts/truetype/padauk/Padauk.ttf',0x104f)

if False:
    import svgwrite
    svg = svgwrite.Drawing(filename = "tryme.svg")
    polyline = svgwrite.shapes.Polyline(points, stroke="black", stroke_width=10, fill="white")
    svg.add(polyline)
    svg.save()
    import subprocess
    print "About to load inkscape, please wait a bit..."
    subprocess.call(['inkscape', 'tryme.svg'])
    print "Did it work? You tell me, I'm just a computer so I can't tell."
    if not result[0].on_curve:
        result.append(result[1])
        # And now make sure we START with an on-curve point
        result = result[1:]
    print "Original points list:"
    print points
    print
    print "Points list with interpolated on-curve points:"
    print result

#    if not os.path.exists(opts.inputfilenamappend(e):
#        print "File {} not found or not accessible".format(opts.inputfilename)
#        sys.exit(2)
#    font = fontforge.open(opts.inputfilename)
#    font[opts.glyphname].export(opts.exportname)
#    font.close()
