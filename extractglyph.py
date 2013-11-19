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

if __name__ == "__main__":
    opts, args = parse_args()
    if not os.path.exists(opts.inputfilename):
        print "File {} not found or not accessible".format(opts.inputfilename)
        sys.exit(2)
    font = fontforge.open(opts.inputfilename)
    font[opts.glyphname].export(opts.exportname)
    font.close()
