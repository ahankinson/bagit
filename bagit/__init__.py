#!/usr/bin/env python

"""
BagIt is a directory, filename convention for bundling an arbitrary set of 
files with a manifest, checksums, and additional metadata. More about BagIt
can be found at:

    http://purl.org/net/bagit

bagit.py is a pure python drop in library and command line tool for creating 
BagIt directories:

    import bagit
    bagit.make_bag('example-directory', {'Contact-Name': 'Ed Summers'})

Basic usage is to give bag a directory to bag up:

    % bagit.py my_directory

You can bag multiple directories if you wish:

    % bagit.py directory1 directory2

Optionally you can pass metadata intended for the bag-info.txt:

    % bagit.py --source-organization "Library of Congress" directory

For more help see:

    % bagit.py --help 
"""

import os
import hashlib
import logging
import optparse
import multiprocessing

from datetime import date

# standard bag-info.txt metadata
bag_info_headers = [
    'Source-Organization', 
    'Organization-Address', 
    'Contact-Name', 
    'Contact-Phone', 
    'Contact-Email',
    'External-Description', 
    'External-Identifier',
    'Bag-Size', 
    'Bag-Group-Identifier', 
    'Bag-Count',
    'Internal-Sender-Identifier', 
    'Internal-Sender-Description',
    # Bagging Date is autogenerated
    # Payload-Oxum is autogenerated
]
def make_bag(bag_dir, bag_info=None, processes=1):
    """
    Convert a given directory into a bag. You can pass in arbitrary 
    key/value pairs to put into the bag-info.txt metadata file as 
    the bag_info dictionary.
    """
    logging.info("creating bag for directory %s" % bag_dir)

    if not os.path.isdir(bag_dir):
        logging.error("no such bag directory %s" % bag_dir)
        raise RuntimeError("no such bag directory %s" % bag_dir)

    old_dir = os.path.abspath(os.path.curdir)
    os.chdir(bag_dir)

    try:
        logging.info("creating data dir")
        os.mkdir('data')

        for f in os.listdir('.'):
            if f == 'data': continue
            new_f = os.path.join('data', f)
            logging.info("moving %s to %s" % (f, new_f))
            os.rename(f, new_f)

        logging.info("writing manifest-md5.txt")
        Oxum = _make_manifest('manifest-md5.txt', 'data', processes)

        logging.info("writing bagit.txt")
        txt = """BagIt-Version: 0.96\nTag-File-Character-Encoding: UTF-8\n"""
        open("bagit.txt", "w").write(txt)

        logging.info("writing bag-info.txt")
        bag_info_txt = open("bag-info.txt", "w")
        if bag_info == None:
            bag_info = {}
        bag_info['Bagging-Date'] = date.strftime(date.today(), "%Y-%m-%d")
        bag_info['Payload-Oxum'] = Oxum
        headers = bag_info.keys()
        headers.sort()
        for h in headers:
            bag_info_txt.write("%s: %s\n"  % (h, bag_info[h]))
        bag_info_txt.close()

    except Exception, e:
        logging.error(e)

    finally:
        os.chdir(old_dir)

def _make_manifest(manifest_file, data_dir, processes):
    logging.info('writing manifest with %s processes' % processes)
    pool = multiprocessing.Pool(processes=processes)
    manifest = open(manifest_file, 'w')
    num_files = 0
    total_bytes = 0
    for digest, filename, bytes in pool.map(_manifest_line, _walk(data_dir)):
        num_files += 1
        total_bytes += bytes
        manifest.write("%s  %s\n" % (digest, filename))
    manifest.close()
    return "%s.%s" % (total_bytes, num_files)

def _walk(data_dir):
    for dirpath, dirnames, filenames in os.walk(data_dir):
        for fn in filenames:
            yield os.path.join(dirpath, fn)

def _manifest_line(filename):
    fh = open(filename)
    m = hashlib.md5()
    total_bytes = 0
    while True:
        bytes = fh.read(16384)
        total_bytes += len(bytes)
        if not bytes: break
        m.update(bytes)
    fh.close()
    return (m.hexdigest(), filename, total_bytes)

# following code is used for command line program

class BagOptionParser(optparse.OptionParser):
    def __init__(self, *args, **opts):
        self.bag_info = {}
        optparse.OptionParser.__init__(self, *args, **opts)

def bag_info_store(option, opt, value, parser):
    opt = opt.lstrip('--')
    opt_caps = '-'.join([o.capitalize() for o in opt.split('-')])
    parser.bag_info[opt_caps] = value

def make_opt_parser():
    parser = BagOptionParser(usage='usage: %prog [options] dir1 dir2 ...')
    parser.add_option('--processes', action='store', type="int", 
                      dest='processes', default=1, 
                      help='parallelize checksums generation')
    parser.add_option('--log', action='store', dest='log')
    parser.add_option('--quiet', action='store_true', dest='quiet')

    for header in bag_info_headers:
        parser.add_option('--%s' % header.lower(), type="string", 
                          action='callback', callback=bag_info_store)
    return parser

def configure_logging(opts):
    log_format="%(asctime)s - %(levelname)s - %(message)s"
    if opts.quiet:
        level = logging.ERROR
    else:
        level = logging.INFO
    if opts.log:
        logging.basicConfig(filename=opts.log, level=level, format=log_format)
    else:
        logging.basicConfig(level=level, format=log_format)

if __name__ == '__main__':
    opt_parser = make_opt_parser()
    opts, args = opt_parser.parse_args()
    configure_logging(opts)
    for bag_dir in args:
        make_bag(bag_dir, bag_info=opt_parser.bag_info, 
                       processes=opts.processes)