import glob
import os
import sys
import settings
import md5
import logging
from pprint import pprint
from wotparse import extract_headers, decompress_file, decrypt_file, extract_version_and_blevel

log = logging.getLogger()

def create_db():
    c = settings.db_conn.cursor()
    ddl = "create table if not exists matchdata (battlehash text primary key, version text, player_side int, outcome text, mapname text, battletier int, gamemode text, gametype text, player_team_kills int, opfor_team_kills int, "
    x = []
    for t in range(1, 16):
        x.append("player_team_tank_{}".format(t))
        x.append("opfor_team_tank_{}".format(t))
    ddl += ", ".join(x)
    ddl += ")"
    c.execute(ddl)
    c.close()


def get_team_frags(players, fragdata):
    rosters = {player: x['team'] for player, x in players['vehicles'].items()}
    frags = {1: 0, 2: 0}

    for player, kills in fragdata[2].items():
        frags[int(rosters[player])] += kills['frags']

    return frags


def get_match_hash(details, mapname):
    p = sorted([str(vdata['accountDBID']) for vehicle, vdata in details['vehicles'].items()])
    s = sorted([str(vdata['damageDealt']) for vehicle, vdata in details['vehicles'].items()])
    return md5.new(mapname + ''.join(s + p)).hexdigest()


def save_match_data(mdata):
    create_db()
    dml = "insert into matchdata ({}) values({})"

    data = {
        'battlehash': mdata['hash'],
        'player_side': mdata['playerSide'],
        'version': mdata['replayVersion'],
        'outcome': mdata['outcome'],
        'mapname': mdata['map'],
        'gamemode': mdata['gamemode'],
        'gametype': mdata['gametype'],
        'battletier': mdata['battleTier'] or 0
    }

    opfor = 2 if 1 == int(mdata['playerSide']) else 1
    data['player_team_kills'] = mdata['teams'][mdata['playerSide']]['kills']
    data['opfor_team_kills'] = mdata['teams'][opfor]['kills']

    x = 1
    for tank in mdata['teams'][mdata['playerSide']]['vehicles']:
        data['player_team_tank_{}'.format(x)] = tank
        x += 1

    x = 1
    for tank in mdata['teams'][opfor]['vehicles']:
        data['opfor_team_tank_{}'.format(x)] = tank
        x += 1

    dml = dml.format(','.join(data.keys()), ("?," * len(data.keys()))[:-1])
    c = settings.db_conn.cursor()
    try:
        c.execute(dml, tuple(data.values()))
        settings.db_conn.commit()
        c.close()
        return True
    except Exception as e:
        log.warn(e)
        return False


def process_file(fname):
    matchData = {
        'map': '',
        'gamemode': '',
        'gametype': '',
        'replayVersion': '',
        'outcome': '',
        'playerSide': '',
        'battleTier': 0,
        'hash': '',
        'teams': {
            1: {'vehicles': [], 'kills': 0},
            2: {'vehicles': [], 'kills': 0},
        },
    }

    try:
        players, frags, details, boff = extract_headers(fname)
    except TypeError:
        return False

    if not players:
        return False

    # Process players fragment
    matchData['map'] = players['mapDisplayName']
    matchData['gamemode'] = players['gameplayID']

    playerName = players['playerName']
    for playerID, player in players['vehicles'].items():
        matchData['teams'][player['team']]['vehicles'].append(player['vehicleType'])
        if player['name'] == playerName:
            matchData['playerSide'] = player['team']

    if int(frags[0]['isWinner']) == 1:
        matchData['outcome'] = 'win'
    elif int(frags[0]['isWinner']) == -1:
        matchData['outcome'] = 'loss'
    else:
        matchData['outcome'] = 'draw'

    matchData['hash'] = get_match_hash(details, matchData['map'])

    frags = get_team_frags(players, frags)
    matchData['teams'][1]['kills'] = frags[1]
    matchData['teams'][2]['kills'] = frags[2]

    decfile = decrypt_file(fname, boff)
    outfile = decompress_file(decfile)
    version, blevel = extract_version_and_blevel(outfile)

    matchData['battleTier'] = blevel
    matchData['replayVersion'] = version
    matchData['gametype'] = settings.GAME_TYPES[int(details['common']['bonusType'])]

    log.info("Match hash {}, version {}".format(matchData['hash'], matchData['replayVersion']))
    log.info("Match outcome: {}".format(matchData['outcome']))
    log.info("Save result: {}".format(save_match_data(matchData)))

    os.unlink(decfile)
    os.unlink(outfile)
    return True


def safe_rename(f, dstdir):
    bf = os.path.basename(f)
    nname = dstdir + "/" + bf
    if os.path.exists(nname):
        os.unlink(f)
    else:
        os.rename(f, nname)


def fail_file(f):
    safe_rename(f, settings.FAIL_DIR)


def ok_file(f):
    safe_rename(f, settings.DONE_DIR)


def process_dir(dirname):
    files = glob.glob(dirname + "/*.wotreplay")
    for f in files:
        bf = os.path.basename(f)
        print "Processing {}".format(bf)
        if process_file(f):
            ok_file(f)
        else:
            fail_file(f)


if __name__ == "__main__":
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        if os.path.isdir(sys.argv[1]):
            process_dir(sys.argv[1])
        elif os.path.isfile(sys.argv[1]):
            process_file(sys.argv[1])
