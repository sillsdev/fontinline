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
def extraction_demo():
    fname = '/usr/share/fonts/truetype/padauk/Padauk.ttf'
    padauk = fontforge.open(fname)
    pa = padauk[0x1015] # U+1015 MYANMAR LETTER PA
    layer = pa.foreground
    print "U+1015 has {} layer(s)".format(len(layer))
    # Result was 1: so there is exactly one contour. If there were more, we'd
    # loop through them each in turn.
    contour = layer[0]
    for point in contour:
        print "({},{}) is an {}-curve point".format(point.x, point.y, ("on" if point.on_curve else "off"))
    # Note that there may be several off-curve points in a sequence, as with
    # the U+1015 example I chose here. The FontForge Python documentation at
    # one point talks about "the TrueType idiom where an on-curve point mid-way
    # between its control points may be omitted, leading to a run of off-curve
    # points (with implied but unspecified on-curve points between them)."

if __name__ == "__main__":
    opts, args = parse_args()
    if not os.path.exists(opts.inputfilename):
        print "File {} not found or not accessible".format(opts.inputfilename)
        sys.exit(2)
    font = fontforge.open(opts.inputfilename)
    font[opts.glyphname].export(opts.exportname)
    font.close()
