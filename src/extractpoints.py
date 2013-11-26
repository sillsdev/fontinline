#!/usr/bin/env python

import fontforge
import optparse
import sys
import os, os.path
import itertools

def parse_args():
    "Parse the arguments the user passed in"
    parser = optparse.OptionParser(description="Demonstrate parsing arguments")
    #parser.add_option('--help', help="Print the help string")
    parser.add_option('-v', '--verbose', action="store_true", help="Give more verbose error messages")
    parser.add_option('-i', '--input', action="store", dest="inputfilename", help="Font file (SFD or TTF format)")
    parser.add_option('-g', '--glyph', action="store", dest="glyphname", help="Glyph name to extract")
    opts, args = parser.parse_args()
    opts.exportname = opts.glyphname + '.svg'
    return opts, args

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
    contour = layer[0]
    points = list(contour)
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
    source2 = source[1:]
    source2 = itertools.islice(source, 1, None)
    for a, b in itertools.izip(source, source2):
        yield (a, b)

if __name__ == "__main__":
    opts, args = parse_args()
    points=extraction_demo('/usr/share/fonts/truetype/padauk/Padauk.ttf',0x1015)
    result = []
    for a, b in pairwise(points):
        if a.on_curve or b.on_curve:
            # No need to extrapolate for this pair
            result.append(a)
        else:
            midpoint = averagepoint(a, b)
            result.append(a)
            result.append(midpoint)
    # Last point will not have been part of any pairs, so it won't have been
    # appended. Append it now.
    result.append(points[-1])
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
