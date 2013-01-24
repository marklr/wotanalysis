<<<<<<< HEAD
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
from pprint import pprint
import cPickle as pickle
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
            f.seek(4, 0)
            nblocks = struct.unpack("i", f.read(4))[0]
            log.info("Got {} blocks in replay {}".format(nblocks, os.path.basename(fn)))
            if nblocks < 3:
                log.warn("Replay {} is incomplete".format(os.path.basename(fn)))
                return None, None, None, None
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
                    return None, None, None, None

                return players, frags, results, f.tell()
    except EOFError:
        log.warn("Could not read file {}".format(fn))
    except IOError:
        log.warn("Could not read file {}".format(fn))
    except ValueError as e:
        log.warn("Error: " + str(e))
    except:
        log.warn(traceback.format_exc())
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


def extract_roster(f):
    log.info("Attempting to find roster offset around {}".format(f.tell()))
    cp = f.tell()
    f.seek(33, 1)

    offsets = (32, 33, 34, )
    for off in offsets:
        try:
            f.seek(cp + off, 0)
            roster = pickle.load(f)
            if roster:
                log.info("Found roster at {}".format(cp + off))
                return roster
        except:
            pass
    log.info("Didn't find roster")
    return None


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

            offsets = [14, 13, 15]
            co = f.tell()
            blevel = {}
            for off in offsets:
                try:
                    f.seek(co + off, 0)
                    blevel = pickle.load(f)
                    log.debug("Battle level {}".format(blevel))
                except:
                    continue

            roster = extract_roster(f)
            blevel = blevel.get('battleLevel', 0)
            return version, blevel, roster
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
        decfile = None
        outfile = None
        if os.path.isdir(sys.argv[1]):
            files = glob.glob(sys.argv[1] + "/*.wotreplay")
        else:
            files = (sys.argv[1], )
        try:
            for fname in files:
                log.info("Processing {}".format(fname))
                players, frags, details, boff = extract_headers(fname)

                if not boff or players is None:
                    log.warn("Could not extract headers from {}".format(fname))
                    continue

                decfile = decrypt_file(fname, boff)
                outfile = decompress_file(decfile)
                os.unlink(decfile)

                version, bt, roster = extract_version_and_blevel(outfile)
                os.unlink(outfile)

                print "-" * 80
                print "Filename: {}".format(fname)
                print "Match version {}, battle tier {}".format(version, bt)
                print "Player data"
                print "-" * 80
                pprint(players)

                print ""
                print "Frag data"
                print "-" * 80
                pprint(frags)

                print ""
                print "Match details"
                print "-" * 80
                pprint(details)

                print ""
                print "Extra roster data (not always present)"
                pprint(roster)

        except:
            log.error(traceback.format_exc())
=======
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
from pprint import pprint
import cPickle as pickle
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
            f.seek(4, 0)
            nblocks = struct.unpack("i", f.read(4))[0]
            log.info("Got {} blocks in replay {}".format(nblocks, os.path.basename(fn)))
            if nblocks < 3:
                log.warn("Replay {} is incomplete".format(os.path.basename(fn)))
                return None, None, None, None
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
                    return None, None, None, None

                return players, frags, results, f.tell()
    except EOFError:
        log.warn("Could not read file {}".format(fn))
    except IOError:
        log.warn("Could not read file {}".format(fn))
    except ValueError as e:
        log.warn("Error: " + str(e))
    except:
        log.warn(traceback.format_exc())
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


def extract_roster(f):
    log.info("Attempting to find roster offset around {}".format(f.tell()))
    cp = f.tell()
    f.seek(33, 1)

    offsets = (32, 33, 34, )
    for off in offsets:
        try:
            f.seek(cp + off, 0)
            roster = pickle.load(f)
            if roster:
                log.info("Found roster at {}".format(cp + off))
                return roster
        except:
            pass
    log.info("Didn't find roster")
    return None


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

            offsets = [14, 13, 15]
            co = f.tell()
            blevel = {}
            for off in offsets:
                try:
                    f.seek(co + off, 0)
                    blevel = pickle.load(f)
                    log.debug("Battle level {}".format(blevel))
                except:
                    continue

            roster = extract_roster(f)
            blevel = blevel.get('battleLevel', 0)
            return version, blevel, roster
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
        decfile = None
        outfile = None
        if os.path.isdir(sys.argv[1]):
            files = glob.glob(sys.argv[1] + "/*.wotreplay")
        else:
            files = (sys.argv[1], )
        try:
            for fname in files:
                log.info("Processing {}".format(fname))
                players, frags, details, boff = extract_headers(fname)

                if not boff or players is None:
                    log.warn("Could not extract headers from {}".format(fname))
                    continue

                decfile = decrypt_file(fname, boff)
                outfile = decompress_file(decfile)
                os.unlink(decfile)

                version, bt, roster = extract_version_and_blevel(outfile)
                os.unlink(outfile)

                print "-" * 80
                print "Filename: {}".format(fname)
                print "Match version {}, battle tier {}".format(version, bt)
                print "Player data"
                print "-" * 80
                pprint(players)

                print ""
                print "Frag data"
                print "-" * 80
                pprint(frags)

                print ""
                print "Match details"
                print "-" * 80
                pprint(details)

                print ""
                print "Extra roster data (not always present)"
                pprint(roster)

        except:
            log.error(traceback.format_exc())
>>>>>>> Minor parse/store changes
