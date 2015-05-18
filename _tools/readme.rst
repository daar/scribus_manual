Automated Wiki to RST Conversion
================================

These are the main scripts used to migrate the wiki.

* ``blmw_to_rst_migrate.py``
  Reads in the XML dump of the manual and writes out RST files into ``./migration/rst_manual/``.

* ``blmw_to_rst.py``:
  The main script to manage conversion from wiki to RST. *(not executed directly)*

* ``rst_image_scrape.py``:
  Scans for ``*.rst`` files and downloads images from ``wiki.blender.org`` into ``./images/``.
  Images are only downloaded as needed, so executing a second time updates.


Example use:

.. code-block:: shell

   python3 blmw_to_rst_migrate.py

   python3 rst_image_scrape.py

   ln -s images migration/rst_manual/images

   sphinx-build migration/rst_manual migration/html_manual

Now you view the output in ``migration/html_manual/contents.html``

