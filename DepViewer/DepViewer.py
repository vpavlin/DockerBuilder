#!/usr/local/bin/python2.7
# encoding: utf-8

import sys
import os
import logging
import re, json
import docker

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter

logging.basicConfig()
logger = logging.getLogger('DepViewer')
format = logging.Formatter("%(levelname)s: %(message)s")
logger.setLevel(logging.INFO)

def warning(msg):
    logger.warning('*** %s' % msg)
    
def fail(msg):
    logger.error(msg)
    sys.exit(1)

class DepViewer():
    client = None
    id = None
    all = False
    images = None

    def __init__(self, all=None):

        if all:
            self.all = all
        self.client = docker.Client(timeout=3600)
        self._loadImages()

    def _getMetaData(self, id):
        meta =  self.client.inspect_image(id)
        return meta

    def _getParent(self, id=None, meta=None):

        if not meta and not id:
            fail("Provide ID or metadata for image")

        if not meta:
            meta = self._getMetaData(id)

        if "Parent" in meta:
            return meta["Parent"]

        fail("Parent id not found.")
    
    def _loadImages(self):
        self.images = self.client.images()

    def _getNames(self, id):
        for image in self.images:
            if id in image["Id"]:
                return image["RepoTags"] if "RepoTags" in image else ""
        
        return ""

    def getDepsList(self, id):
        image_list = []
        
        parent = self._getParent(id)
        names = self._getNames(id)

        image_list.append("%s %s" % (id, names))

        while parent != "":
            names = self._getNames(parent)
            image_list.append("%s %s" % (parent, names))

            parent = self._getParent(parent)

        return image_list

        

    def printDeps(self, id):

        parent = self._getParent(id)
        names = self._getNames(id)

        if all and names:
            print("%s %s" % (id, names))
        i = 1
        while parent != "":
            indent = ""
            names = self._getNames(parent)
            for _ in range(0, i):
                indent += " "

            if all and names:
                print("%s%s %s" % (indent,parent,names))
                i += 1

            parent = self._getParent(parent)



def main(argv=None): # IGNORE:C0111
    '''Command line options.'''

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    parser = ArgumentParser(description=DepViewer, formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument("-a", "--all", dest="all", default=False, action='store_true', help="Show all images")
    parser.add_argument("id", nargs=1)

    args = parser.parse_args()

    dv = DepViewer(args.all)
    dv.printDeps(args.id[0])

if __name__ == "__main__":
    sys.exit(main())
