#!/usr/bin/env python3

import os

def source_list(path, filename_check=None):
    for dirpath, dirnames, filenames in os.walk(path):

        for filename in filenames:
            if filename_check is None or filename_check(filename):
                yield os.path.join(dirpath, filename)

import subprocess
CWD = "."
URL_PREFIX = "http://wiki.scribus.net/canvas/File:"
OUT = "images"

images = set()
for f in source_list(CWD, filename_check=lambda f: f.endswith(".rst")):
    print(f)
    for l in open(f, encoding="utf-8"):
        if " figure::" in l:
            # maybe many figures in a table
            for w in l.split("|"):
                if " figure::" in w:
                    image = w.split("::", 1)[1].strip()
                    # remove: `/images/`
                    image = image.split("/", 2)[2]
                    image = image.strip("|+ ")
                    images.add(image)

import urllib.parse

os.system("mkdir " + OUT)
for i, image in enumerate(sorted(images)):

    image_final = os.path.join(OUT, image)

    if os.path.exists(image_final):
        #print("Found:", image)
        continue
    else:
        print("Download:", image, "%d of %d" % (i + 1, len(images)))


    URL = URL_PREFIX + urllib.parse.quote(image)
    cmd = (
        'wget',
        URL,
        '-O', 'tmp.html',
        '--quiet',
        )
    #print("#", cmd)
    subprocess.call(cmd)
    URL_REAL = None
    for h in open("tmp.html", encoding="utf-8"):
        if "fullImageLink" in h:
            URL_REAL = h.split('<a href="')[2].split('"', 1)[0]
            break
    if URL_REAL:
        cmd = (
            'wget',
            "http://wiki.scribus.net" + URL_REAL,
            '-O', image_final,
            '--quiet'
            )

        #print(cmd)
        subprocess.call(cmd)
    else:
        print("IMAGE NOT FOUND", image)

