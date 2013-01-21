# Sources:
# http://archive.wotreplays.ru/parser.py.txt
# http://blog.wot-replays.org/
# https://raw.github.com/raszpl/wotrepparser/master/wotrepparser.py

import logging
import struct
import json
import os
import sys
import re
import traceback
import zlib
import glob
from blowfish import Blowfish

try:
    import cPickle as pickle
except ImportError:
    import pickle

import settings

log = logging.getLogger()


def extract_headers(fn):
    """
    Extracts and returns a tuple of the following data structures, plus the offset of the compress archive stream
    * players
    * frags
    * detailed battle results

    TODO:
    * Figure out what the "details" key means
    """
    try:
        with open(fn, "rb") as f:
            f.seek(4)
            nblocks = struct.unpack("i", f.read(4))[0]
            if nblocks == 1:
                log.warn("Replay is incomplete")
                return None
            else:
                bs = struct.unpack("i", f.read(4))[0]
                players = json.loads(f.read(bs).decode('utf-8'))
                log.info("Loaded player data, {} bytes".format(bs))

                bs = struct.unpack("i", f.read(4))[0]
                frags = json.loads(f.read(bs).decode('utf-8'))
                log.info("Loaded frag data, {} bytes".format(bs))

                bs = struct.unpack("i", f.read(4))[0]
                try:
                    results = pickle.loads(f.read(bs))
                    log.info("Loaded battle results, {} bytes".format(bs))
                except pickle.UnpicklingError as e:
                    log.warn("Could not load battle results")
                    log.warn(e)
                    return None

                return players, frags, results, f.tell()
    except EOFError:
        log.warn("Could not read file {}".format(fn))
    except IOError:
        log.warn("Could not read file {}".format(fn))
    except ValueError as e:
        log.warn("Error: " + str(e))
    return None, None, None, None


def decrypt_file(fn, offset=0):
    bc = 0
    pb = None
    bf = Blowfish(settings.BLOWFISH_KEY)
    log.info("Decrypting from offset {}".format(offset))
    of = fn + ".tmp"
    with open(fn, 'rb') as f:
        f.seek(offset)
        with open(of, 'wb') as out:
            while True:
                b = f.read(8)
                if not b:
                    break

                if len(b) < 8:
                    b += '\x00' * (8 - len(b))  # pad for correct blocksize

                if bc > 0:
                    db = bf.decrypt(b)
                    if pb:
                        db = ''.join([chr(ord(a) ^ ord(b)) for a, b in zip(db, pb)])

                    pb = db
                    out.write(db)
                bc += 1
            return of
    return None


def decompress_file(fn):
    log.info("Decompressing")
    with open(fn, 'rb') as i:
        with open(fn + '.out', 'wb') as o:
            o.write(zlib.decompress(i.read()))
            return fn + ".out"
        os.unlink(fn)


def extract_version_and_blevel(fn):
    try:
        with open(fn, 'rb') as f:

            f.seek(12, 0)
            bs = struct.unpack("i", f.read(4))[0]
            version = f.read(bs)
            x = re.match("^World.*?of.*?Tanks v\.(\d+)\.(\d+)\.(\d+)\s#(\d+)", version.replace('\xc2\xa0', ' '))
            version = '.'.join(x.groups()[:-1]) + ' ' + x.groups()[-1]
            log.info("Replay version {}".format(version))

            f.seek(35, 1)
            bs = int(struct.unpack("b", f.read(1))[0])
            playername = f.read(bs)
            log.info("Player name {}".format(playername))

            f.seek(14, 1)
            blevel = pickle.load(f)
            log.debug("Battle level {}".format(blevel))

            if 'battleLevel' in blevel:
                return version, blevel['battleLevel']
            else:
                return version, 0
            # log.info("Roster offset: {}".format(bs + 33))
            # f.seek(33, 1)
            # roster = pickle.load(f)
            # pprint(roster)
    except IOError as e:
        log.warn(e)
        return None, None


def extract_chats(fn):
    with open(fn, 'rb') as f:
        s = f.read()
        p = re.compile(r'<font.*>.*?</font>')
        return p.findall(s)

if __name__ == "__main__":
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        if os.path.isdir(sys.argv[1]):
            files = glob.glob(sys.argv[1] + "/*.wotreplay")
        else:
            files = (sys.argv[1], )
        try:
            for fname in files:
                #players, frags, details, boff = extract_headers(fname)
                #outfile = decompress_file(decrypt_file(fname, boff))
                extract_version_and_blevel(fname)
        except:
            log.error(traceback.format_exc())
