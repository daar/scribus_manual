#!/usr/bin/env python3

import xml.dom.minidom
import blmw_to_rst
import os
import shutil

MANUAL_PATH = 'migration/rst_manual'
USE_MULTIPROCESS = True

def rst_title(title, char, single=True):
    if single:
        l = len(title)
        t = char * l
        return title + "\n" + t
    else:
        if char == "%":
            t_pre = " "
            t_post = "  "
        else:
            t_pre = "  "
            t_post = " "

        title = t_pre + title + t_post
        l = len(title)
        t = char * l

        return t + "\n" + title + "\n" + t


def create_conf():
    src = "../conf.py"
    dst = os.path.join(MANUAL_PATH, "conf.py")
    shutil.copyfile(src, dst)


def create_contents(paths, flat=False):

    with open(os.path.join(MANUAL_PATH, "contents.rst"), 'w', encoding='utf-8') as f:
        fw = f.write

        fw(rst_title("Scribus Manual contents", "%", single=False))
        fw("\n\n")

        fw(".. toctree::\n\n")

        if flat:
            for fn_full, fn in paths:
                fw("   %s\n" % fn)
        else:
            paths_index = []
            paths_other = []
            for fn_full, fn in paths:
                path_base = fn.split(os.sep)[0]
                if path_base.endswith(".rst"):
                    paths_other.append((fn_full, fn))
                    continue
                if path_base not in paths_index:
                    fw("   %s/index.rst\n" % path_base)
                    paths_index.append(path_base)
            fw("\n\n")

            # these don't really fit, adding anyway
            for fn_full, fn in paths_other:
                    fw("   %s\n" % fn)


            for path_base in paths_index:
                with open(os.path.join(MANUAL_PATH, path_base, "index.rst"), 'w', encoding='utf-8') as fi:
                    fiw = fi.write
                    fiw(".. _%s-index:\n\n" % path_base)

                    fiw(rst_title(path_base.replace("_", "_").title(), "#", single=False))
                    fiw("\n\n")
                    fiw(".. toctree::\n\n")
                    for fn_full, fn in paths:
                        if fn.startswith(path_base + os.sep):
                            fiw("   %s\n" % fn[len(path_base) + 1:])


def main():
    # Load the whole wiki manual xml export from MediaWiki
    with open('migration/scribus_wiki.xml', encoding='utf-8') as f:
        node = xml.dom.minidom.parse(f)

    # Look into every 'page' node and build a page for it, saving it in a path
    # that mirrors the original MediaWiki path (and the title of the page)


    # collect paths for re-use
    paths = []
    if USE_MULTIPROCESS:
        args = []

    for n in node.getElementsByTagName('page'):
        for title in n.getElementsByTagName('title'):
            page_title = title.firstChild.nodeValue
            # Strip the "Help" namespace, make all lowercase
            page_path = page_title[5:].lower()
            # Remove whitespaces
            page_path = page_path.replace(" ", "_")
            # Remove "'"
            page_path = page_path.replace("'", "")
            print(page_path)
        for text in n.getElementsByTagName('text'):
            page_text = text.firstChild.nodeValue

        #if not "vitals/" in page_path:
        #    continue

        # Check if the filepath exsits, otherwise create it
        page_dir = os.path.join(MANUAL_PATH, os.path.dirname(page_path))
        if not os.path.exists(page_dir):
            os.makedirs(page_dir)

        # We actually run the parser against the text tag content
        page_path_rst = page_path + ".rst"
        page_path_rst_full = os.path.join(MANUAL_PATH, page_path_rst)
        arg = page_text, page_path_rst_full
        if USE_MULTIPROCESS:
            args.append(arg)
        else:
            blmw_to_rst.example_usage(*arg)
        paths.append((page_path_rst_full, page_path_rst))


    if USE_MULTIPROCESS:
        import multiprocessing
        job_total = multiprocessing.cpu_count()
        pool = multiprocessing.Pool(processes=job_total * 2) 
        pool.map(blmw_to_rst.example_usage_mp, args)

    create_conf()
    create_contents(paths)

if __name__ == "__main__":
    main()

    print("To build:")
    print("  sphinx-build %s %s" % (MANUAL_PATH, MANUAL_PATH.replace("rst", "html")))

