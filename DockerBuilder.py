#!/usr/local/bin/python2.7
# encoding: utf-8
'''
DockerBuilder -- Build Dockerfiles repository

DockerBuilder is a hmm?

It defines classes_and_methods

@author:     Václav Pavlín

@copyright:  2014 Red Hat. All rights reserved.

@license:    license

@contact:    vpavlin@redhat.com
'''

import sys
import os, io
import logging
import tempfile
import shutil
import time, datetime
import re, json

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
import ConfigParser
from git import Repo
import docker

__version__ = "0.1"
__updated__ = "2014-06-17"
__date__ = "2014-06-01"

logging.basicConfig()
logger = logging.getLogger('DockerBuilder')
format = logging.Formatter("%(levelname)s: %(message)s")
logger.setLevel(logging.INFO)

def read_conf(conf_file):
    conf = ConfigParser.ConfigParser()
    conf.readfp(open(conf_file))
    return conf

def scrub_list(alist):
    """
    Take a comma-separate list, split on the commas, and scrub out any leading
    or trailing whitespace for each element.
    """
    return [p.strip() for p in alist.split(',')]

def warning(msg):
    logger.warning('*** %s' % msg)
    
def fail(msg):
    logger.error(msg)
    sys.exit(1)

class DockerBuilder():
    ropts = ['source', 'errlog']
    debug = False
    repo_path = None
    source = None
    builddirs = None   
    buildpaths = {} 
    repo = None
    dryrun = False
    source = None
    errlog = "err.log"
    recurse = False
    tag = None
    push = False
    save = False
    keep_containers = False
    

    def __init__(self, conf=None, debug=False, source=None, builddirs=None, errlog=None, recurse=False, dryrun=False, tag=None, push=False, save=False, keep_containers=False):
        '''
        Constructor
        '''
        
        if conf != None:
            self._checkConf(conf)
            
        if debug:
            self.debug = debug
        
        if self.debug:    
            logger.setLevel(logging.DEBUG)
            
        if source:
                self.source = source   
        elif not self.source:
            fail("No source GIT repo specified")
        
        if builddirs:
                self.builddirs = scrub_list(builddirs)   
            
        if errlog:
                self.errlog = errlog   
            
        if recurse:
            self.recurse = recurse
            
        if dryrun:
            self.dryrun = dryrun
            
        if tag:
            self.tag = scrub_list(tag)
            
        if push:
            self.push = push

        if save:
            self.save = save
 
        if keep_containers:
            self.keep_containers = keep_containers
           
            
        self.repo_path = tempfile.mkdtemp()
        self.client = docker.Client(timeout=3600)
    
    def __del__(self):
        if self.repo_path and os.path.exists(self.repo_path) and self.debug:
            shutil.rmtree(self.repo_path)

    
    def _checkConf(self, conf):
        """
        Ensure the config file makes sense. 'conf' can be a path to the config
        file or the ConfigParser object itself after reading one.
        """
        
        logger.info('Checking config file options')
        conf = read_conf(conf)
        
        try:
            self.source = conf.get('DockerBuild', 'source')
        except ConfigParser.NoSectionError:
            self._fail('DockerBuild is not a section in your config file')
        except ConfigParser.NoOptionError:
            self._fail('"source" option in DockerBuild section is missing')
        # the subclasses have these options in per-repo sections
        for o in conf.options('DockerBuild'):
            if o == 'tag' or o == 'builddirs':
                setattr(self, o, scrub_list(conf.get('DockerBuild', o)))
            elif o in ('recurse', 'push', 'dryrun', 'save', 'keep_containers'):
                setattr(self, o, conf.getboolean('DockerBuild', o))
            else:
                setattr(self, o, conf.get('DockerBuild', o))
            if o not in self.ropts:
                warning('useless option found: %s' % o)
            logger.info('  %s = %s' % (o, getattr(self, o)))
        for option in self.ropts:
            if getattr(self, option, None) == None:
                self._fail('Missing option: %s' % option)
    
    def prepareBuildroot(self):
        '''Download repo'''
        logger.info('Clonning %s to %s' % (self.source, self.repo_path))
        self.source = Repo.clone_from(self.source, self.repo_path)
        logger.info('Done %s' % (self.source))
        
    def checkBuildDirs(self):
        if self.builddirs:
            for dir in self.builddirs:
                self._checkBuildDir(os.path.join(self.repo_path, dir))
        else:
            self._checkBuildDir(self.repo_path)
    
    def _addBuildPath(self, name, path):
        self.buildpaths[name] = {'path': path, 'id': None}
        
    def _addBuildId(self, name, id):
        self.buildpaths[name]["id"] = id
            
    def _checkBuildDir(self, path):
        logger.info("Checking %s" % (path))
        if os.path.isfile(os.path.join(path, "Dockerfile")):
            self._addBuildPath(self._getImageName(path), path)
            logger.info("Dockerfile found")
        elif self.recurse:
            for d in os.listdir(path):
                if os.path.isdir(os.path.join(path, d)) and not d.startswith("."):
                    self._checkBuildDir(os.path.join(path,d))

    def _writeError(self, f, stream_list):
        for l in stream_list:
            j = json.loads(l)
            if 'stream' in j:
                f.write(j['stream'])
            elif 'error' in j:
                f.write(j['error'])
            else:
                f.write(l)


                    
    def build(self):
        _errlog = str(time.time())+"-"+self.errlog
        with open(_errlog, 'w') as f:
            f.write("Starting a build at %s\n" % datetime.datetime.now())
            for name, item in self.buildpaths.iteritems():
                #name = self._getImageName(p)
                logger.info("Building %s" % name)
                starttime = time.time()
                if not self.dryrun:
                    stream = self.client.build(path=item["path"], nocache=True, tag=name, stream=False, rm=True)
                    l = list(stream)
                    last_line = json.loads(l[-1])
                    
                    id = None
                    if 'stream' in last_line:
                        logger.info("Last stream line: %s" % l[-1])
                        match_id = re.search(r'.*Successfully built ([a-z0-9]+)', last_line['stream'])
                        if match_id:
                            id = match_id.group(1)
                    if not id:
                        if 'error' in last_line:
                            logger.error(last_line['error'])
                            self._writeError(f, l)
                            logger.error("Build of the image %s failed. See %s for more details." % (name, _errlog))
                            if not self.keep_containers:
                                self._removeArtefacts(name)
                            continue

                    self._addBuildId(name, id)
                    endtime = time.time()
                    logger.info("Image %s built with id %s in %i s" % (name, id, (endtime-starttime)))
                if self.tag:
                    self._tagImage(name)

                if id and self.save:
                    self._saveContainer(id, name)
                    

        logger.info(self.buildpaths)
    
    def _getImageName(self, path):
        from_image = None
        dockerfile = open(os.path.join(path, "Dockerfile"))
        srch = r'\s*FROM\s+([^# \t\n:]+)'
        for l in dockerfile:
            match = re.search(srch, l)
            if match:
                from_image = match.group(1)
                break
        dockerfile.close()
        tmpdir = os.path.basename(self.repo_path)
        sub = None
        leftdir = path
        path_name = []
        while (tmpdir != sub):
            if sub and not sub.startswith("."):
                path_name.append(sub)
            sub = os.path.basename(leftdir)
            leftdir = os.path.dirname(leftdir)
            
        path_name.reverse()
        name = "%s-%s" % (from_image.split("/")[-1], '-'.join(path_name))
        if self.repo:
            name = "%s/%s" % (self.repo, name)
        return name
    
    def _tagImage(self, name):
        if not self.tag:
            logger.error("Na tags specified!")
            return
        for t in self.tag:
            logger.info("Tagging image %s to registry %s" % (name, t))
            if not self.dryrun:
                self.client.tag(name, os.path.join(t, name))
            if self.push:
                logger.info("Pushing image %s to registry %s" % (name, t))
                if not self.dryrun:
                    self.client.push(os.path.join(t, name))

    def _removeArtefacts(self, name):
        self.client.remove_image(name)
        if self.tag:
            for t in self.tag:
                self.client.remove_image(os.path.join(t, name))

    def _saveContainer(self, id, name):
        path, filename = name.split("/")
        save_name = os.path.join(path, filename+".tar")
        if not os.path.isdir(path):
            os.mkdir(path)
        with open(save_name, 'wb') as fi:
            fi.write(self.client.get_image(id).read())

        if not self.keep_containers and os.path.isfile(save_name):
            self._removeArtefacts(name)

def main(argv=None): # IGNORE:C0111
    '''Command line options.'''

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    program_name = os.path.basename(sys.argv[0])
    program_version = "v%s" % __version__
    program_build_date = str(__updated__)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    program_shortdesc = __import__('__main__').__doc__.split("\n")[1]
    program_license = '''%s

  Created by user_name on %s.
  Copyright 2014 organization_name. All rights reserved.

  Licensed under the Apache License 2.0
  http://www.apache.org/licenses/LICENSE-2.0

  Distributed on an "AS IS" basis without warranties
  or conditions of any kind, either express or implied.

USAGE
''' % (program_shortdesc, str(__date__))

   # try:
        # Setup argument parser
    parser = ArgumentParser(description=program_license, formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument("--debug", dest="debug", default=False, action='store_true', help="Enable debug mode")
    parser.add_argument("-c", "--config", dest="config", help="config file containing info about repo and build")
    parser.add_argument("-v", "--verbose", dest="verbose", action="count", help="set verbosity level [default: %(default)s]")
    parser.add_argument("-s", "--source", dest="source", help="GIT repository containing Dockerfiles")
    parser.add_argument("-b", "--builddirs", dest="builddirs", help="List of directories in repo which should be searched for Dockerfiles")
    parser.add_argument("-e", "--errlog", dest="errlog", help="File where output of the failed build will be stored")
    parser.add_argument("-r", "--recurse", dest="recurse", default=False, action='store_true', help="Recurse into subdirectories")
    parser.add_argument("--dry-run", dest="dryrun", default=False, action='store_true', help="Do not build, tag or push anything - just print output as if...")
    parser.add_argument("-t", "--tag", dest="tag", help="List of registries image should be tagged to")
    parser.add_argument("-p", "--push", dest="push", default=False, action='store_true', help="Push built images")
    parser.add_argument("--save", dest="save", default=False, action='store_true', help="Save images locally and remove them from local Docker storage")
    parser.add_argument("--keep-containers", dest="keep_containers", default="False", action='store_true', help="Do not remove intermediate containers after build")
 #    parser.add_argument('-V', '--version', action='version', version=program_version_message)
     
    # Process arguments
    args = parser.parse_args()
    verbose = args.verbose
    debug = args.debug

    if verbose > 0:
        print("Verbose mode on")

    db = DockerBuilder(args.config, args.debug, args.source, args.builddirs, args.errlog, args.recurse, args.dryrun, args.tag, args.push, args.save, args.keep_containers)
    db.prepareBuildroot()
    db.checkBuildDirs()
    db.build()
     

    
    

if __name__ == "__main__":
    sys.exit(main())
