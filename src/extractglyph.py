#!/usr/bin/env python

import fontforge
import optparse
import sys
import os, os.path

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
    for point in contour:
        pointlist.append([(point.x,point.y),point.on_curve])
        print "({},{}) is an {}-curve point".format(point.x, point.y, ("on" if point.on_curve else "off"))
    return pointlist
    # Note that there may be several off-curve points in a sequence, as with
    # the U+1015 example I chose here. The FontForge Python documentation at
    # one point talks about "the TrueType idiom where an on-curve point mid-way
    # between its control points may be omitted, leading to a run of off-curve
    # points (with implied but unspecified on-curve points between them)."
    
def averagepoint(point1,point2):
    avgpoint=[]
    i=0
    while i<len(point1):
        avgpoint.append((point1[i]+point2[i])/2.0)
        i=i+1
    return tuple(avgpoint)

if __name__ == "__main__":
    opts, args = parse_args()
    points=extraction_demo('/usr/share/fonts/truetype/padauk/Padauk.ttf',0x1015)
    i=0
    while i<len(points)-1:
        if points[i][1]==0 and points[i+1][1]==0:
            points=points[:i+1]+[[averagepoint(points[i][0],points[i+1][0]),1]]+points[i+1:]
        i=i+1
    print points
#    if not os.path.exists(opts.inputfilenamappend(e):
#        print "File {} not found or not accessible".format(opts.inputfilename)
#        sys.exit(2)
#    font = fontforge.open(opts.inputfilename)
#    font[opts.glyphname].export(opts.exportname)
#    font.close()
